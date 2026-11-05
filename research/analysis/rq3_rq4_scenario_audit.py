#!/usr/bin/env python3
"""Aggregate-only RQ3/RQ4 audit. Scenarios are NOT observational business evidence."""
import argparse,json
from pathlib import Path
import pandas as pd,numpy as np

def read(p):
    return pd.read_csv(p) if p.suffix.lower()==".csv" else pd.read_excel(p)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--rq3",type=Path,required=True)
    p.add_argument("--rq4",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    r=read(a.rq3);q=read(a.rq4)
    required={"stock_at_cutoff","synthetic_future_30_day_oracle_demand_units",
      "baseline_order_qty","trend_policy_order_qty","baseline_cost_bdt_scenario",
      "trend_cost_bdt_scenario","baseline_lost_units_scenario","trend_lost_units_scenario"}
    assert required<=set(r.columns),"RQ3 required scenario fields missing"
    assert {"action","evidence_complete","constraint_reason","suggested_order_qty_scenario"}<=set(q.columns)
    delta=r.trend_cost_bdt_scenario-r.baseline_cost_bdt_scenario
    out={"rq3":{"scope":"synthetic-oracle scenario only, not actual savings",
      "cases":int(len(r)),"baseline_cost_bdt":float(r.baseline_cost_bdt_scenario.sum()),
      "trend_cost_bdt":float(r.trend_cost_bdt_scenario.sum()),
      "trend_minus_baseline_cost_bdt":float(delta.sum()),
      "baseline_lost_units":float(r.baseline_lost_units_scenario.sum()),
      "trend_lost_units":float(r.trend_lost_units_scenario.sum()),
      "initial_stock_sufficient_fraction":float((r.stock_at_cutoff>=r.synthetic_future_30_day_oracle_demand_units).mean()),
      "mean_initial_stock":float(r.stock_at_cutoff.mean()),
      "mean_oracle_future_demand":float(r.synthetic_future_30_day_oracle_demand_units.mean()),
      "baseline_order_positive_cases":int((r.baseline_order_qty>0).sum()),
      "trend_order_positive_cases":int((r.trend_policy_order_qty>0).sum()),
      "fraction_equal_cost":float((delta==0).mean())},
      "rq4":{"scope":"structured evidence case audit, not human usability",
      "cases":int(len(q)),"actions":q.action.value_counts().to_dict(),
      "reasons":q.constraint_reason.fillna("MISSING").value_counts().to_dict(),
      "evidence_flagged_complete":int(q.evidence_complete.astype(str).str.upper().eq("YES").sum()),
      "evidence_flag_independently_verified":False,
      "human_comprehension_test_executed":False}}
    (a.out/"rq3_rq4_aggregate_audit.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
    print(json.dumps(out,indent=2))
if __name__=="__main__":main()
