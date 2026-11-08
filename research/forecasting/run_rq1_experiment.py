"""Reproducible RQ1 development experiment; this script generates no data."""
from __future__ import annotations
import argparse, hashlib, json, platform, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

KEYS = ["shop_id", "category"]
HORIZONS = [1, 7, 14, 28]
ORIGINS = pd.to_datetime(["2025-07-01", "2025-08-01", "2025-09-01"])
WINDOWS, LAGS = [7, 14, 28, 56], [1, 7, 14, 28, 56]
DEV_END = "2025-10-01"

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def load_panel(path):
    d = pd.read_csv(path, parse_dates=["date"])
    required = {"shop_id", "category", "date", "units_sold_observed", "is_zero_observed_sales"}
    if not required.issubset(d.columns): raise ValueError(f"Missing columns: {sorted(required-set(d.columns))}")
    if d[list(required)].isna().any().any(): raise ValueError("Missing required values")
    if d.duplicated(KEYS+["date"]).any(): raise ValueError("Duplicate shop-category-date keys")
    d["demand"] = pd.to_numeric(d.units_sold_observed, errors="raise")
    if (d.demand < 0).any() or not np.isfinite(d.demand).all(): raise ValueError("Demand must be finite and non-negative")
    if not np.array_equal(d.is_zero_observed_sales.astype(int), (d.demand == 0).astype(int)):
        raise ValueError("Zero-sales flag mismatch")
    expected = pd.date_range(d.date.min(), d.date.max(), freq="D")
    for key, g in d.groupby(KEYS, sort=False):
        if not pd.DatetimeIndex(g.date.sort_values()).equals(expected):
            raise ValueError(f"Incomplete daily panel for {key}; do not fill missing dates blindly")
    return d.sort_values(KEYS+["date"]).reset_index(drop=True)

def regime(y):
    y = np.asarray(y, float); p = y[y > 0]
    if not len(p): return "no_observed_demand"
    adi = len(y)/len(p); cv2 = (p.std()/p.mean())**2 if p.mean() else np.inf
    if adi >= 1.32 and cv2 >= .49: return "lumpy"
    if adi >= 1.32: return "intermittent"
    if cv2 >= .49: return "erratic"
    return "smooth"

def features(y, origin):
    y = np.asarray(y, float)
    if len(y) < 56: raise ValueError("At least 56 historical days required")
    f = {f"lag_{k}": float(y[-k]) for k in LAGS}
    for w in WINDOWS:
        a = y[-w:]
        f.update({f"mean_{w}": float(a.mean()), f"std_{w}": float(a.std()),
                  f"sum_{w}": float(a.sum()), f"zero_{w}": float((a == 0).mean())})
    p = y[y > 0]
    f["days_since_sale"] = float(len(y)-1-np.flatnonzero(y > 0)[-1]) if len(p) else float(len(y))
    f["adi"] = float(len(y)/len(p)) if len(p) else float(len(y)+1)
    f["positive_mean"] = float(p.mean()) if len(p) else 0.0
    f["positive_cv2"] = float((p.std()/p.mean())**2) if len(p) and p.mean() else 0.0
    f.update(dow=origin.dayofweek, day=origin.day, month=origin.month,
        week=int(origin.isocalendar().week), dow_sin=np.sin(2*np.pi*origin.dayofweek/7),
        dow_cos=np.cos(2*np.pi*origin.dayofweek/7),
        month_sin=np.sin(2*np.pi*(origin.month-1)/12),
        month_cos=np.cos(2*np.pi*(origin.month-1)/12))
    return f

def training_rows(panel, horizon, cutoff):
    rows = []
    for (shop, cat), g in panel.groupby(KEYS, sort=False):
        g = g.sort_values("date"); y = g.demand.to_numpy(float); dates = pd.DatetimeIndex(g.date)
        # Historical training origins are sampled every 90 days; labels end before cutoff.
        for i in range(56, len(y)-horizon+1, 90):
            if dates[i] >= cutoff or dates[i+horizon-1] >= cutoff: break
            f = features(y[:i], dates[i])
            f.update(shop_id=shop, category=cat, target=float(y[i:i+horizon].sum()))
            rows.append(f)
    return pd.DataFrame(rows)

def seasonal_naive(y, horizon):
    vals = []
    for j in range(horizon):
        idx = len(y)-1-j
        prior = [y[idx-k] for k in (7, 14, 21, 28) if idx-k >= 0]
        vals.append(float(np.mean(prior)) if prior else float(np.mean(y[-7:])))
    return max(0.0, float(np.sum(vals)))

def croston_classic(y, alpha=.1):
    y = np.asarray(y, float); nz = np.flatnonzero(y > 0)
    if not len(nz): return 0.0
    size, interval, gap = float(y[nz[0]]), float(nz[0]+1), 1
    for i in range(nz[0]+1, len(y)):
        if y[i] > 0:
            size = alpha*y[i]+(1-alpha)*size
            interval = alpha*gap+(1-alpha)*interval
            gap = 1
        else: gap += 1
    return max(0.0, size/max(interval, 1e-9))

def score(y, pred):
    y, pred = np.asarray(y, float), np.maximum(0, np.asarray(pred, float)); den = np.abs(y).sum()
    return {"n": len(y), "actual_total": float(y.sum()), "forecast_total": float(pred.sum()),
        "wape": float(np.abs(y-pred).sum()/den) if den else np.nan,
        "mae": float(mean_absolute_error(y,pred)),
        "rmse": float(np.sqrt(mean_squared_error(y,pred))),
        "mean_error": float((pred-y).mean()),
        "signed_bias_pct": float((pred-y).sum()/den) if den else np.nan}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input", required=True); ap.add_argument("--output", required=True)
    ap.add_argument("--evidence-status", default="provenance_conflict")
    a=ap.parse_args(); src=Path(a.input); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    started=time.time(); panel=load_panel(src); diag=[]
    for (shop,cat),g in panel.groupby(KEYS,sort=False):
        y=g.demand.to_numpy(float); p=y[y>0]
        diag.append({"shop_id":shop,"category":cat,"n_days":len(y),"positive_days":len(p),
            "zero_ratio":float((y==0).mean()),"ADI":float(len(y)/len(p)) if len(p) else np.inf,
            "CV2_positive":float((p.std()/p.mean())**2) if len(p) and p.mean() else np.inf,
            "total_units":float(y.sum()),"regime":regime(y)})
    pd.DataFrame(diag).to_csv(out/"demand_regime_diagnostics.csv",index=False)
    preds=[]; summaries=[]
    for h in HORIZONS:
        for origin in ORIGINS:
            train=training_rows(panel,h,origin); rows=[]; actual=[]; histories=[]; regimes=[]
            for (shop,cat),g in panel.groupby(KEYS,sort=False):
                g=g.sort_values("date"); hist=g[g.date<origin].demand.to_numpy(float)
                fut=g[(g.date>=origin)&(g.date<origin+pd.Timedelta(days=h))]
                if len(hist)<56 or len(fut)!=h: continue
                f=features(hist,origin); f.update(shop_id=shop,category=cat)
                rows.append(f); actual.append(float(fut.demand.sum())); histories.append(hist); regimes.append(regime(hist))
            test=pd.DataFrame(rows); y=np.asarray(actual,float)
            if train.empty or test.empty:
                summaries.append({"horizon":h,"origin":str(origin.date()),"status":"insufficient_data"}); continue
            cats=["shop_id","category"]; cols=[c for c in train.columns if c!="target"]
            for c in cats:
                train[c]=train[c].astype("category")
                test[c]=pd.Categorical(test[c],categories=train[c].cat.categories)
            model=lgb.LGBMRegressor(objective="tweedie",tweedie_variance_power=1.3,
                n_estimators=80,learning_rate=.035,num_leaves=31,min_child_samples=80,
                subsample=.85,colsample_bytree=.85,reg_lambda=2.0,random_state=42,n_jobs=-1,verbosity=-1)
            model.fit(train[cols],train.target,categorical_feature=cats)
            candidates={"lightgbm_tweedie":np.maximum(0,model.predict(test[cols])),
                "seasonal_naive_7":np.array([seasonal_naive(z,h) for z in histories]),
                "croston_classic":np.array([croston_classic(z)*h for z in histories])}
            for name,pred in candidates.items():
                m=score(y,pred); summaries.append({"horizon":h,"origin":str(origin.date()),
                    "model":name,"status":"ok","train_rows":len(train),"test_series":len(test),**m})
                for i in range(len(y)):
                    preds.append({"horizon":h,"origin":str(origin.date()),"shop_id":test.iloc[i].shop_id,
                        "category":test.iloc[i].category,"regime":regimes[i],"model":name,
                        "actual":y[i],"forecast":pred[i]})
        print(f"Completed horizon {h}",flush=True)
    pdp=pd.DataFrame(preds); pdp.to_csv(out/"rolling_origin_predictions.csv",index=False)
    pd.DataFrame(summaries).to_csv(out/"rolling_origin_metrics.csv",index=False)
    agg=[]
    for (h,m),g in pdp.groupby(["horizon","model"]):
        agg.append({"horizon":h,"model":m,**score(g.actual,g.forecast),"origins":g.origin.nunique()})
    pd.DataFrame(agg).sort_values(["horizon","wape"]).to_csv(out/"model_comparison_development.csv",index=False)
    h7=pdp[pdp.horizon==7]; rows=[]
    for (m,r),g in h7.groupby(["model","regime"]):
        den=np.abs(g.actual).sum()
        rows.append({"model":m,"regime":r,"n":len(g),"actual_total":g.actual.sum(),
            "wape":np.abs(g.actual-g.forecast).sum()/den if den else np.nan,
            "mean_error":(g.forecast-g.actual).mean()})
    pd.DataFrame(rows).to_csv(out/"regime_metrics_h7.csv",index=False)
    manifest={"pipeline":"rq1_empirical_development_v1","input_file":src.name,"input_sha256":sha256(src),
        "rows":len(panel),"series":int(panel.groupby(KEYS).ngroups),"shops":int(panel.shop_id.nunique()),
        "categories":int(panel.category.nunique()),"date_start":str(panel.date.min().date()),
        "date_end":str(panel.date.max().date()),"development_origins":[str(x.date()) for x in ORIGINS],
        "development_end_exclusive":DEV_END,"horizons":HORIZONS,"evidence_status":a.evidence_status,
        "final_holdout_evaluated":False,"legacy_q4_2025_excluded":True,"training_origin_stride_days":90,
        "model":"LightGBM Tweedie direct cumulative horizon; categorical shop/category",
        "comparators":["weekly seasonal naive","classic Croston average-rate diagnostic"],
        "limitations":["provenance conflict unresolved","sales are not unconstrained demand",
            "three development origins only","no hyperparameter search","no calibrated intervals",
            "no final holdout","classic Croston is not SBA/TSB"],
        "elapsed_seconds":time.time()-started,"python":sys.version,"platform":platform.platform()}
    (out/"run_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(pd.DataFrame(agg).sort_values(["horizon","wape"]).to_string(index=False))
if __name__=="__main__": main()
