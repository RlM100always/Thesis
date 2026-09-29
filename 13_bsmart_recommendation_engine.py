"""B-SMART Strategy Recommendation engine (Algorithm 1, thesis_report/Chapters/
proposedMethod.tex, sec:sequential_procedure) -- a real, runnable implementation
of the algorithm, not a diagram of it.

Runs against this repo's Bangladesh-pharmacy dataset (built by
00a_generate_pharmacy_dataset.py -- real medicine catalog + real BD demand
shape + labeled-synthetic transaction linkage, see
normalized_data/DATASET_MANIFEST.md):
  - normalized_data/fact_transactions.csv + dim_product.csv + dim_customer.csv
    (all 111 SKUs are real Bangladeshi medicines; no category slice is needed
    any more since the whole dataset is pharmacy-vertical) for reorder
    candidate actions.
  - output/customer_features.csv + normalized_data/dim_customer.csv
    (Marketing_Consent) + output/models/retrained_churn_model.pkl (the ACTUAL
    leak-free model trained by 09_retrain_models.py) for retention candidate
    actions.

No number here is fabricated: every rate, price, margin and probability is
computed from the CSVs/models actually present in this repo, and every
business constant that ISN'T in the data (lead time, pack size, budget cap,
contact cost, service level, risk weight) is declared as an explicit
ASSUMPTION up front and printed with the results, per the thesis's own rule
that "uncertain values will be investigated by sensitivity analysis, not
considered as known numbers" (proposedMethod.tex, sec:formal_problem_formulation).

Writes:
  output/bsmart_recommendations.json        R_t -- top-K feasible actions
  output/bsmart_candidate_actions_audit.csv every candidate, feasible or not
  output/bsmart_run_summary.json            counts for citing on slides
  output/figures/bsmart_top_recommendations.png
  output/figures/bsmart_worked_example.png
  output/figures/bsmart_funnel.png
  output/figures/bsmart_churn_scores.png
"""
import utf8_console  # noqa: F401
import json
import math
import pickle
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SEED = 42
np.random.seed(SEED)

OUT = Path("output")
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- declared assumptions --
# None of these constants exist as measured values in this dataset (no
# supplier/purchase-order table, and Marketing_Consent is a business-consent
# flag, not a cost/lead-time figure). They are fixed here, once, and printed
# with every run so a reader can re-derive every downstream number by hand.
ASSUMPTIONS = {
    "lead_time_days": 5,          # no supplier table in this dataset
    "pack_multiple": 10,           # typical pharmacy strip/pack size
    "service_z": 1.65,             # 95% cycle service level (standard OR constant)
    "carrying_rate": 0.02,         # matches api/analytics_routes.py's live constant
    "lambda_risk": 0.5,            # weight on the uncertainty term of U(a)
    # Real medicine prices here are BDT 1.5-35/unit (see PRICE_BAND_BDT in
    # 00a_generate_pharmacy_dataset.py), so an absolute BDT budget would now be
    # meaningful -- kept as a share of this cutoff's own identified reorder
    # need anyway, since no specific owner-declared budget figure exists yet.
    "reorder_budget_fraction": 0.40,
    "contact_cost_bdt": 5.0,       # matches api/analytics_routes.py's live constant
    "retention_uplift": 0.12,      # matches api/analytics_routes.py's live constant
    # --- pharmacy-specific constraints (PHARMACY_VERTICAL_SCOPE guideline §6) ---
    "min_shelf_life_days": 180,    # minimum remaining shelf life accepted at purchase
    "near_expiry_days": 120,       # batch inside this window is a near-expiry risk
    "expiry_markdown_pct": 0.30,   # markdown needed to clear near-expiry stock
    "expiry_writeoff_share": 0.60, # share of near-expiry stock lost if no action taken
    # Storage is shared across every SKU, so a single order may not consume
    # more than this share of the branch's free shelf / fridge space.
    "storage_share_per_action": 0.15,
    # Business policy: prescription-only medicines may not be pushed at a
    # customer through a marketing contact (DGDA schedule + ethics).
    "promote_prescription_only": False,
    # Campaign capacity (PHARMACY_VERTICAL_SCOPE guideline §6): a shop with
    # three staff cannot ring 990 customers in a cycle. Consent says who MAY
    # be contacted; capacity says how many actually CAN be.
    "campaign_capacity_per_cycle": 150,
    "top_k": 15,
    # R_t is a pharmacy owner's action list for one day, not a leaderboard.
    # A pure global sort on U(a) is dominated by whichever action type has the
    # largest BDT magnitude -- here retention, because a customer's lifetime
    # value dwarfs the margin on one cheap medicine line. That would hand the
    # owner 15 phone calls and zero stock actions, which is operationally
    # useless. R_t therefore reserves a quota per action type and ranks by
    # U(a) WITHIN each type; unused quota is redistributed by utility.
    "top_k_quota": {"reorder": 5, "expiry": 5, "retention": 5},
}
STOCK_URGENCY = {"Out-of-Stock": 2.0, "Low": 1.5, "Medium": 1.0, "High": 0.0}


def log(step, msg):
    print(f"[Algorithm 1 | step {step}] {msg}")


# ============================================================ STEP 1-2: VALIDATE, SNAPSHOT
def build_snapshot():
    log(1, "validating sources and schema")
    fact = pd.read_csv("normalized_data/fact_transactions.csv",
                       parse_dates=["Transaction_Date", "Expiry_Date"])
    product = pd.read_csv("normalized_data/dim_product.csv")
    customer = pd.read_csv("normalized_data/dim_customer.csv")
    assert fact["Transaction_Date"].notna().all(), "unparseable transaction timestamps"
    assert "Expiry_Date" in fact.columns, "pharmacy schema requires Expiry_Date (batch shelf life)"

    # Every SKU in this dataset is a real Bangladeshi pharmacy medicine (see
    # normalized_data/DATASET_MANIFEST.md) -- no category slice needed.
    sales = (
        fact.merge(product, on="Product_ID")
        .merge(customer[["Customer_ID", "Division"]], on="Customer_ID", how="left")
    )
    cutoff = fact["Transaction_Date"].max()
    log(2, f"snapshot X_t frozen at cutoff t = {cutoff.date()} ({len(sales)} pharmacy rows of {len(fact)} total)")
    return sales, cutoff


# ============================================================ STEP 3-4: MODEL LADDER + DEMAND
def monthly_series(df, start, end):
    idx = pd.period_range(start, end, freq="M")
    s = df.set_index("Transaction_Date")["Quantity"].resample("ME").sum()
    s.index = s.index.to_period("M")
    return s.reindex(idx, fill_value=0.0)


def gate_demand_model(monthly_qty):
    """Real model-ladder gate: an EWMA candidate is promoted over the plain-mean
    baseline only if it beats it on a 3-month held-out tail -- the same
    promotion rule proposedMethod.tex describes (candidate must show a material,
    consistent improvement on held-out evidence before it is trusted)."""
    if len(monthly_qty) < 9:
        return "baseline", float(monthly_qty.mean()), float(monthly_qty.std(ddof=0))
    dev, test = monthly_qty.iloc[:-3], monthly_qty.iloc[-3:]
    baseline_pred = float(dev.mean())
    ewma_dev = dev.ewm(span=6, adjust=False).mean()
    model_pred = float(ewma_dev.iloc[-1])
    baseline_err = abs(test.sum() - baseline_pred * 3)
    model_err = abs(test.sum() - model_pred * 3)
    selected = "model" if model_err < baseline_err else "baseline"
    ewma_full = monthly_qty.ewm(span=6, adjust=False).mean()
    rate = float(ewma_full.iloc[-1]) if selected == "model" else float(monthly_qty.mean())
    residual_std = float((dev - ewma_dev).std(ddof=0)) if selected == "model" else float(dev.std(ddof=0))
    return selected, rate, residual_std


def build_reorder_candidates(sales, cutoff):
    log(3, "comparing baseline vs EWMA candidate per (division, SKU) on a 3-month held-out tail")
    start = cutoff - pd.DateOffset(months=47)
    candidates = []
    gate_counts = {"model": 0, "baseline": 0}
    for (product_name, division), grp in sales.groupby(["Product_Name", "Division"]):
        if division is None or (isinstance(division, float) and math.isnan(division)):
            continue
        if len(grp) < 12:
            continue  # eligibility rule: too short a series to fit any candidate honestly
        monthly_qty = monthly_series(grp, start, cutoff)
        selected, monthly_rate, monthly_resid_std = gate_demand_model(monthly_qty)
        gate_counts[selected] += 1
        daily_rate = monthly_rate / 30.0
        daily_resid_std = monthly_resid_std / 30.0

        last_status = grp.sort_values("Transaction_Date")["Stock_Level"].iloc[-1]
        urgency = STOCK_URGENCY.get(last_status, 1.0)
        if urgency == 0.0:
            continue  # real business rule: sufficiently stocked SKU needs no action

        price = float(grp["Unit_Price_BDT"].mean())
        margin_pct = float(grp["Profit_Margin_Percent"].mean())
        unit_cost = price * (1 - margin_pct / 100.0)
        margin_per_unit = price - unit_cost

        lead = ASSUMPTIONS["lead_time_days"]
        lead_demand = daily_rate * lead * urgency
        safety = ASSUMPTIONS["service_z"] * daily_resid_std * math.sqrt(lead)

        # --- inventory position: IP = on-hand + on-order - backorder ---------
        # Ordering against gross demand double-orders whatever is already in
        # transit, and under-orders whatever is already owed to a customer.
        latest = grp.sort_values("Transaction_Date").iloc[-1]
        incoming = float(latest.get("Incoming_Stock_Units", 0) or 0)
        backorder = float(latest.get("Backorder_Units", 0) or 0)
        raw_qty = max(lead_demand + safety + backorder - incoming, 0.0)

        pack = ASSUMPTIONS["pack_multiple"]
        reorder_qty = int(math.ceil(raw_qty / pack) * pack) if raw_qty > 0 else 0
        if reorder_qty <= 0:
            continue  # incoming stock already covers lead-time demand

        # --- pharmacy-specific: shelf-life cap -------------------------------
        # A medicine ordered today must be sellable before it expires. Cap the
        # order at what this SKU's own demand rate can clear within the minimum
        # accepted remaining shelf life, so the algorithm cannot recommend
        # stock that is structurally destined to be written off. Generic
        # retail reorder logic has no equivalent of this constraint.
        shelf_days = ASSUMPTIONS["min_shelf_life_days"]
        sellable_before_expiry = daily_rate * shelf_days
        shelf_capped = False
        if sellable_before_expiry > 0 and reorder_qty > sellable_before_expiry:
            capped = int(math.floor(sellable_before_expiry / pack) * pack)
            if capped <= 0:
                continue  # cannot clear even one pack before expiry -- do not order
            reorder_qty, shelf_capped = capped, True

        # --- MOQ: the supplier will not ship below its minimum --------------
        moq = int(latest.get("MOQ_Units", 0) or 0)
        moq_raised = False
        if moq and reorder_qty < moq:
            # Raising to MOQ is only honest if the larger quantity still clears
            # before expiry; otherwise the order is infeasible, not adjustable.
            if sellable_before_expiry > 0 and moq > sellable_before_expiry:
                continue
            reorder_qty, moq_raised = moq, True

        # --- storage / cold chain: the order has to physically fit -----------
        cold = bool(latest.get("Cold_Chain_Required", False))
        capacity = float(latest.get(
            "Cold_Chain_Capacity_Units" if cold else "Storage_Capacity_Units", 0) or 0)
        allowance = capacity * ASSUMPTIONS["storage_share_per_action"]
        storage_capped = False
        if allowance > 0 and reorder_qty > allowance:
            capped = int(math.floor(allowance / pack) * pack)
            if capped < max(moq, pack):
                continue  # cannot fit even a shippable quantity -- abstain
            reorder_qty, storage_capped = capped, True

        benefit = min(reorder_qty, math.ceil(lead_demand)) * margin_per_unit
        cost = reorder_qty * unit_cost * ASSUMPTIONS["carrying_rate"]
        risk = ASSUMPTIONS["lambda_risk"] * daily_resid_std * lead * margin_per_unit
        utility = benefit - cost - risk

        reason = (
            f"{product_name} in {division}: last status '{last_status}', "
            f"{selected}-selected demand {daily_rate:.2f} units/day, "
            f"reorder {reorder_qty} units to cover a {lead}-day lead time at {ASSUMPTIONS['service_z']}-sigma service."
        )
        if shelf_capped:
            reason += (f" Quantity capped to what {shelf_days}-day minimum shelf life allows"
                       f" selling before expiry.")
        if moq_raised:
            reason += f" Raised to the supplier's {moq}-unit minimum order quantity."
        if storage_capped:
            reason += (" Capped to the "
                       f"{'cold-chain' if cold else 'shelf'} space this branch can free.")

        # --- Layer 8: structured, owner-readable explanation ----------------
        # Same numbers as above, but laid out as the evidence a pharmacist
        # would check by hand, plus an explicit per-constraint verdict. This
        # is what the UI renders; `reason` stays as the one-line summary.
        explanation = {
            "action": f"Order {reorder_qty} units of {product_name} ({division})",
            "why": {
                "forecast_demand_over_lead_time": round(lead_demand, 1),
                "safety_stock": round(safety, 1),
                "incoming_stock": incoming,
                "backorder": backorder,
                "lead_time_days": lead,
                "last_stock_status": last_status,
                "demand_model": f"{selected} (EWMA gate vs mean baseline on a 3-month held-out tail)",
            },
            "constraints": {
                "budget": "pending",  # decided in the feasibility pass
                "moq": f"ok (raised to {moq})" if moq_raised else ("ok" if not moq else f"ok (>= {moq})"),
                "pack_size": f"ok (multiple of {pack})",
                "shelf_life": f"capped to {shelf_days}-day clearance" if shelf_capped else "ok",
                "storage": (f"capped to {'cold-chain' if cold else 'shelf'} allowance"
                            if storage_capped else "ok"),
                "cold_chain": "required" if cold else "not required",
            },
            "confidence": "model" if selected == "model" else "baseline",
        }

        candidates.append({
            "type": "reorder", "sku": product_name, "division": division,
            "confidence": selected, "daily_rate": round(daily_rate, 3),
            "last_stock_status": last_status, "reorder_qty": reorder_qty,
            "shelf_life_capped": shelf_capped, "moq_raised": moq_raised,
            "storage_capped": storage_capped, "cold_chain_required": cold,
            "incoming_stock_units": incoming, "backorder_units": backorder,
            "unit_cost_bdt": round(unit_cost, 2), "margin_per_unit_bdt": round(margin_per_unit, 2),
            "reorder_cost_bdt": round(reorder_qty * unit_cost, 2),
            "benefit_bdt": round(benefit, 2), "action_cost_bdt": round(cost, 2),
            "risk_bdt": round(risk, 2), "utility_bdt": round(utility, 2),
            "reason": reason, "explanation": explanation,
            "evidence_source": "normalized_data/fact_transactions.csv (Bangladesh-pharmacy dataset, real medicine SKU)",
            "cutoff": str(cutoff.date()),
        })
    log(4, f"model-ladder gate selected: {gate_counts['model']} EWMA-model, {gate_counts['baseline']} mean-baseline series")
    return candidates


# ============================ STEP 4 (cont): PHARMACY-SPECIFIC NEAR-EXPIRY RISK
def build_expiry_candidates(sales, cutoff):
    """Near-expiry batch risk -- the action type that only exists because this
    is a pharmacy. Stock sitting on a batch that expires inside the
    near-expiry window is money already at risk: either it is cleared at a
    markdown now, or a share of it is written off at expiry. The action is
    recommended only when the margin retained by marking down beats the
    expected write-off, which is a real comparison, not a fixed rule."""
    log(4, "assessing near-expiry batch risk per (SKU, division) -- pharmacy-specific action type")
    near_days = ASSUMPTIONS["near_expiry_days"]
    horizon = cutoff + pd.Timedelta(days=near_days)
    at_risk = sales[(sales["Expiry_Date"] > cutoff) & (sales["Expiry_Date"] <= horizon)]

    candidates = []
    for (product_name, division), grp in at_risk.groupby(["Product_Name", "Division"]):
        units = float(grp["Quantity"].sum())
        if units <= 0:
            continue
        price = float(grp["Unit_Price_BDT"].mean())
        margin_pct = float(grp["Profit_Margin_Percent"].mean())
        unit_cost = price * (1 - margin_pct / 100.0)
        days_left = int((grp["Expiry_Date"].min() - cutoff).days)

        # Marking down keeps (price - markdown) per unit instead of losing
        # expiry_writeoff_share of the units at full cost.
        markdown_price = price * (1 - ASSUMPTIONS["expiry_markdown_pct"])
        margin_if_marked_down = max(markdown_price - unit_cost, 0.0) * units
        loss_if_ignored = units * ASSUMPTIONS["expiry_writeoff_share"] * unit_cost
        benefit = margin_if_marked_down + loss_if_ignored * ASSUMPTIONS["expiry_writeoff_share"]
        cost = units * (price - markdown_price) * ASSUMPTIONS["expiry_writeoff_share"]
        # Less time left = less certainty the markdown clears the stock at all.
        urgency_risk = 1.0 - (days_left / near_days)
        risk = ASSUMPTIONS["lambda_risk"] * urgency_risk * benefit
        utility = benefit - cost - risk
        if utility <= 0:
            continue  # marking down would destroy more value than it saves

        candidates.append({
            "type": "expiry", "sku": product_name, "division": division,
            "confidence": "rule",  # batch dates are recorded facts, not a prediction
            "units_at_risk": round(units, 1), "days_to_earliest_expiry": days_left,
            "unit_cost_bdt": round(unit_cost, 2),
            "benefit_bdt": round(benefit, 2), "action_cost_bdt": round(cost, 2),
            "risk_bdt": round(risk, 2), "utility_bdt": round(utility, 2),
            "reason": (
                f"{product_name} in {division}: {units:.0f} units on batches expiring within "
                f"{near_days} days (earliest in {days_left} days). Clear at "
                f"{ASSUMPTIONS['expiry_markdown_pct']*100:.0f}% markdown before "
                f"{ASSUMPTIONS['expiry_writeoff_share']*100:.0f}% is written off at expiry."
            ),
            "evidence_source": "normalized_data/fact_transactions.csv Expiry_Date (recorded batch shelf life)",
            "cutoff": str(cutoff.date()),
        })
    log(4, f"{len(candidates)} near-expiry actions are worth taking of {at_risk[['Product_Name','Division']].drop_duplicates().shape[0]} (SKU, division) pairs holding at-risk batches")
    return candidates


# ============================================================ STEP 4 (cont): CUSTOMER INACTIVITY
def build_retention_candidates():
    log(4, "scoring customer inactivity with the retrained, leak-free churn model")
    customers = pd.read_csv("output/customer_features.csv")
    consent = pd.read_csv("normalized_data/dim_customer.csv")[["Customer_ID", "Marketing_Consent"]]
    customers = customers.merge(consent, on="Customer_ID", how="left")
    with open("output/models/retrained_churn_model.pkl", "rb") as handle:
        artifact = pickle.load(handle)
    model, features, threshold = artifact["model"], artifact["features"], artifact["threshold"]
    X = customers[features]
    proba = model.predict_proba(X)[:, 1]
    customers = customers.assign(churn_probability=proba)
    ground_truth_churned = (customers["Recency"] > 90).astype(int)

    eligible = customers[(customers["churn_probability"] >= threshold) & (customers["Monetary"] > 0)]
    log(4, f"{len(eligible)} of {len(customers)} customers cross the churn threshold ({threshold:.3f}) with positive lifetime value")

    candidates = []
    for _, row in eligible.iterrows():
        benefit = row["churn_probability"] * ASSUMPTIONS["retention_uplift"] * row["Monetary"]
        cost = ASSUMPTIONS["contact_cost_bdt"]
        uncertainty = 1 - abs(row["churn_probability"] - 0.5) * 2  # near 0.5 = least certain
        risk = ASSUMPTIONS["lambda_risk"] * uncertainty * benefit
        utility = benefit - cost - risk
        candidates.append({
            "type": "retention", "customer_id": row["Customer_ID"],
            "confidence": "model", "churn_probability": round(float(row["churn_probability"]), 4),
            "monetary_bdt": round(float(row["Monetary"]), 2),
            "benefit_bdt": round(benefit, 2), "action_cost_bdt": round(cost, 2),
            "risk_bdt": round(risk, 2), "utility_bdt": round(utility, 2),
            "reason": f"churn probability {row['churn_probability']:.2f} (model threshold {threshold:.2f}), lifetime value ৳{row['Monetary']:.0f}.",
            "evidence_source": "output/models/retrained_churn_model.pkl (09_retrain_models.py, leak-free holdout)",
            "marketing_consent": bool(row["Marketing_Consent"]),
        })
    return candidates, customers, ground_truth_churned, threshold


# ============================================================ STEP 6-13: FEASIBILITY, RANK, R_t
def feasibility_and_rank(reorder_candidates, retention_candidates, expiry_candidates):
    log(8, "checking feasibility: budget cap for reorder, consent gate for retention, shelf-life window for expiry")
    audit = []

    # Near-expiry actions cost shelf margin, not purchasing budget, so they are
    # not gated by the reorder budget. Their own constraint is time: an action
    # is only feasible while there is still shelf life left to sell into.
    for a in expiry_candidates:
        if a["days_to_earliest_expiry"] > 0:
            a["feasible"] = True
            a["infeasible_reason"] = None
        else:
            a["feasible"] = False
            a["infeasible_reason"] = "batch already expired; disposal, not markdown, is the correct action"
        audit.append(a)

    # Consent decides who MAY be contacted; campaign capacity decides how many
    # actually CAN be, so the highest-utility consenting customers get the slots.
    capacity = ASSUMPTIONS["campaign_capacity_per_cycle"]
    consenting = sorted([a for a in retention_candidates if a["marketing_consent"]],
                        key=lambda a: a["utility_bdt"], reverse=True)
    within_capacity = {id(a) for a in consenting[:capacity]}
    for a in retention_candidates:
        if not a["marketing_consent"]:
            a["feasible"] = False
            a["infeasible_reason"] = ("customer has not given marketing consent; B-SMART's strategy "
                                       "layer requires explicit consent before any contact action -- "
                                       "abstaining, per proposedMethod.tex sec 3.2.4.2, is the correct "
                                       "outcome here, not an error.")
        elif id(a) not in within_capacity:
            a["feasible"] = False
            a["infeasible_reason"] = (f"campaign capacity ({capacity} contacts per cycle) is already "
                                       "committed to higher-utility customers; consent is present but "
                                       "the shop cannot physically make this contact this cycle.")
        else:
            a["feasible"] = True
            a["infeasible_reason"] = None
        audit.append(a)

    reorder_sorted = sorted(reorder_candidates, key=lambda a: a["utility_bdt"], reverse=True)
    spent = 0.0
    total_need = sum(a["reorder_cost_bdt"] for a in reorder_candidates)
    budget = total_need * ASSUMPTIONS["reorder_budget_fraction"]
    for a in reorder_sorted:
        if spent + a["reorder_cost_bdt"] <= budget:
            a["feasible"] = True
            a["infeasible_reason"] = None
            spent += a["reorder_cost_bdt"]
            a["explanation"]["constraints"]["budget"] = f"ok (৳{a['reorder_cost_bdt']:,.0f} of ৳{budget:,.0f})"
        else:
            a["feasible"] = False
            a["infeasible_reason"] = f"reorder budget cap (৳{budget:,.0f}) reached; ৳{spent:,.0f} already committed to higher-utility actions"
            a["explanation"]["constraints"]["budget"] = f"BLOCKED (৳{budget:,.0f} cap reached)"
        audit.append(a)

    log(11, f"eliminated infeasible actions; ৳{spent:,.0f} of ৳{budget:,.0f} reorder budget committed")
    feasible = [a for a in audit if a["feasible"]]
    feasible.sort(key=lambda a: a["utility_bdt"], reverse=True)

    # ---- quota-balanced slate construction (see top_k_quota rationale) ------
    quota = dict(ASSUMPTIONS["top_k_quota"])
    by_type = {t: [a for a in feasible if a["type"] == t] for t in quota}
    top_k, used = [], set()
    for t, want in quota.items():
        take = by_type[t][:want]
        top_k.extend(take)
        used.update(id(a) for a in take)
    # Redistribute any unfilled quota to the best remaining actions of any type.
    if len(top_k) < ASSUMPTIONS["top_k"]:
        for a in feasible:
            if len(top_k) >= ASSUMPTIONS["top_k"]:
                break
            if id(a) not in used:
                top_k.append(a)
                used.add(id(a))
    top_k.sort(key=lambda a: a["utility_bdt"], reverse=True)
    mix = {t: sum(1 for a in top_k if a["type"] == t) for t in quota}
    log(13, f"R_t = top-{len(top_k)} of {len(feasible)} feasible actions "
            f"(of {len(audit)} candidates generated); balanced mix {mix}")
    return top_k, audit


def main():
    print("=" * 78)
    print("B-SMART STRATEGY RECOMMENDATION -- Algorithm 1, running end to end")
    print("Assumptions declared before any number is computed:")
    for k, v in ASSUMPTIONS.items():
        print(f"    {k} = {v}")
    print("=" * 78)

    sales, cutoff = build_snapshot()
    reorder = build_reorder_candidates(sales, cutoff)
    expiry = build_expiry_candidates(sales, cutoff)
    retention, customers, ground_truth_churned, threshold = build_retention_candidates()
    r_t, audit = feasibility_and_rank(reorder, retention, expiry)

    OUT.mkdir(exist_ok=True)
    with open(OUT / "bsmart_recommendations.json", "w", encoding="utf-8") as f:
        json.dump({"cutoff": str(cutoff.date()), "assumptions": ASSUMPTIONS, "R_t": r_t}, f, indent=2, default=str)
    pd.DataFrame(audit).to_csv(OUT / "bsmart_candidate_actions_audit.csv", index=False, encoding="utf-8-sig")

    summary = {
        "cutoff": str(cutoff.date()),
        "reorder_candidates_generated": len(reorder),
        "expiry_candidates_generated": len(expiry),
        "retention_candidates_generated": len(retention),
        "total_candidates": len(audit),
        "reorder_feasible": sum(1 for a in audit if a["type"] == "reorder" and a["feasible"]),
        "expiry_feasible": sum(1 for a in audit if a["type"] == "expiry" and a["feasible"]),
        "retention_feasible": sum(1 for a in audit if a["type"] == "retention" and a["feasible"]),
        "top_k_size": len(r_t),
        "r_t_type_mix": {t: sum(1 for a in r_t if a["type"] == t) for t in ("reorder", "expiry", "retention")},
        "reorder_shelf_life_capped": sum(1 for a in reorder if a.get("shelf_life_capped")),
        "reorder_budget_committed_bdt": round(sum(a["reorder_cost_bdt"] for a in r_t if a["type"] == "reorder"), 2),
        "reorder_budget_fraction": ASSUMPTIONS["reorder_budget_fraction"],
        "reorder_total_identified_need_bdt": round(sum(a["reorder_cost_bdt"] for a in reorder), 2),
        "churn_threshold": round(float(threshold), 4),
        "churn_customers_scored": int(len(customers)),
        "churn_customers_above_threshold": len(retention),
    }
    with open(OUT / "bsmart_run_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("\nRUN SUMMARY")
    print(json.dumps(summary, indent=2))

    # ---- figures ----
    top12 = r_t[:12]

    def label_of(a):
        if a["type"] == "reorder":
            return f"Reorder: {a['sku']} · {a['division']}"
        if a["type"] == "expiry":
            return f"Near-expiry: {a['sku']} · {a['division']}"
        return f"Retain: {a['customer_id']}"

    TYPE_COLOR = {"reorder": "#0F7370", "expiry": "#A9660A", "retention": "#7A3FA0"}
    labels = [label_of(a) for a in top12]
    values = [a["utility_bdt"] for a in top12]
    colors = [TYPE_COLOR[a["type"]] for a in top12]
    plt.figure(figsize=(10, 6))
    y = np.arange(len(labels))
    plt.barh(y, values, color=colors)
    plt.yticks(y, labels, fontsize=9)
    plt.gca().invert_yaxis()
    for i, v in enumerate(values):
        plt.text(v + max(values) * 0.01, i, f"BDT {v:,.0f}", va="center", fontsize=8.5)
    plt.xlabel("Utility U(a), BDT")
    plt.title(f"R_t -- Top {len(top12)} Feasible Recommendations at Cutoff {cutoff.date()}")
    handles = [plt.Rectangle((0, 0), 1, 1, color=TYPE_COLOR[t]) for t in ("reorder", "expiry", "retention")]
    plt.legend(handles, ["reorder (budget-gated)", "near-expiry markdown (pharmacy-specific)",
                         "retention (consent-gated)"], loc="lower right", fontsize=8.5)
    plt.tight_layout()
    plt.savefig(FIG / "bsmart_top_recommendations.png", dpi=300, bbox_inches="tight")
    plt.close()

    best = r_t[0]
    stages = ["E[ΔProfit(a)]\n(benefit)", "− ActionCost(a)\n(carrying)", "− λ·Risk(a)\n(uncertainty)", "U(a)\n(utility)"]
    vals = [best["benefit_bdt"], -best["action_cost_bdt"], -best["risk_bdt"], best["utility_bdt"]]
    cum = [vals[0], vals[0] + vals[1], vals[0] + vals[1] + vals[2], vals[0] + vals[1] + vals[2]]
    bottoms = [0, min(vals[0], cum[0]), min(cum[0], cum[1]), 0]
    bar_vals = [vals[0], abs(vals[1]), abs(vals[2]), vals[3]]
    plt.figure(figsize=(8, 5.2))
    bar_colors = ["#0F7370", "#D13E24", "#A9660A", "#142441"]
    plt.bar(stages, bar_vals, bottom=[0, cum[0] if vals[1] < 0 else 0, cum[1] if vals[2] < 0 else 0, 0], color=bar_colors)
    for i, (s, v) in enumerate(zip(stages, vals)):
        plt.text(i, max(bar_vals) * 1.02, f"{v:+,.0f}", ha="center", fontsize=10, fontweight="bold")
    title = best.get("sku") or best.get("customer_id")
    plt.title(f"Worked Example -- {title} ({best.get('division', '')})".strip())
    plt.ylabel("BDT")
    plt.tight_layout()
    plt.savefig(FIG / "bsmart_worked_example.png", dpi=300, bbox_inches="tight")
    plt.close()

    stage_labels = ["Candidates\ngenerated", "Passed stock / shelf-life /\neligibility rule",
                    "Passed budget / consent /\nexpiry-window gate", f"In R_t\n(top-{len(r_t)})"]
    stage_counts = [
        len(audit),
        len(reorder) + len(expiry) + len(retention),
        sum(1 for a in audit if a["feasible"]),
        len(r_t),
    ]
    plt.figure(figsize=(8, 5))
    bars = plt.bar(stage_labels, stage_counts, color=["#94A3B8", "#64748B", "#0F7370", "#142441"])
    plt.yscale("log")
    plt.ylim(0.7, max(stage_counts) * 3)
    for b, v in zip(bars, stage_counts):
        plt.text(b.get_x() + b.get_width() / 2, v * 1.15, str(v), ha="center", fontweight="bold")
    plt.ylabel("Candidate actions (log scale)")
    plt.title("Algorithm 1 Funnel -- Real Counts From This Run")
    retention_passed = sum(1 for a in audit if a["type"] == "retention" and a["feasible"])
    plt.annotate(f"Retention: {retention_passed} of {len(retention)} passed the consent gate\n(Marketing_Consent field, sampled at ~55% opt-in)",
                 xy=(2, sum(1 for a in audit if a['feasible'])), xytext=(1.15, 2.2),
                 fontsize=9, color="#B93B2A", ha="left",
                 arrowprops=dict(arrowstyle="->", color="#B93B2A"))
    plt.tight_layout()
    plt.savefig(FIG / "bsmart_funnel.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.hist(customers.loc[ground_truth_churned == 0, "churn_probability"], bins=25, alpha=0.65, label="Actually retained (Recency ≤ 90d)", color="#0F7370")
    plt.hist(customers.loc[ground_truth_churned == 1, "churn_probability"], bins=25, alpha=0.65, label="Actually churned (Recency > 90d)", color="#D13E24")
    plt.axvline(threshold, color="#142441", linestyle="--", label=f"decision threshold {threshold:.2f}")
    plt.xlabel("Predicted churn probability (retrained_churn_model.pkl)")
    plt.ylabel("Customers")
    plt.title("Real Churn Scores on the Untouched Holdout-Trained Model")
    plt.legend(fontsize=8.5)
    plt.tight_layout()
    plt.savefig(FIG / "bsmart_churn_scores.png", dpi=300, bbox_inches="tight")
    plt.close()

    print("\nFigures written to output/figures/bsmart_*.png")


if __name__ == "__main__":
    main()
