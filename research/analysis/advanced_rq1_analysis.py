#!/usr/bin/env python3
"""Reproducible RQ1 advanced analysis, B-SMART.

Input is the *restricted* 561,152-row shop-category-day source panel.
Outputs are aggregate-only JSON and figures (not customer-level or source rows).
Model-selection on the already reviewed 2025-10..12 period is exploratory.
No independent merchant origin, consent, stockout completeness or multi-sector
validity is established by this script.
"""
import argparse, json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from lightgbm import LGBMRegressor, LGBMClassifier, early_stopping

SEED=42

def score(y,p):
    y=np.asarray(y,float);p=np.maximum(np.asarray(p,float),0)
    a=np.abs(y-p)
    denom=np.abs(y).sum()
    return dict(n=int(len(y)),wape=(float(a.sum()/denom) if denom>0 else None),
        mae=float(a.mean()),rmse=float(np.sqrt(((y-p)**2).mean())),
        actual_units=float(y.sum()),predicted_units=float(p.sum()),
        bias_units=float((p-y).sum()))

def build_features(d):
    d=d.sort_values(["shop_id","category","date"]).reset_index(drop=True)
    g=d.groupby(["shop_id","category"],sort=False)["units_sold_observed"]
    for lag in (1,7,14,28):d[f"lag_{lag}"]=g.shift(lag)
    for win in (7,28):
        d[f"roll_{win}"]=g.transform(lambda s:s.shift(1).rolling(win,min_periods=win).mean())
    d["dow"]=d.date.dt.dayofweek
    d["month"]=d.date.dt.month
    d["dayofyear"]=d.date.dt.dayofyear
    d=d.dropna(subset=["lag_28","roll_28"]).reset_index(drop=True)
    for c in ("shop_id","category"):d[c]=d[c].astype("category")
    return d

FEATS=["shop_id","category","lag_1","lag_7","lag_14","lag_28",
       "roll_7","roll_28","dow","month","dayofyear"]

def refit(d,train,valid,n_estimators=300):
    m=LGBMRegressor(n_estimators=n_estimators,learning_rate=.06,
        num_leaves=31,max_depth=7,min_child_samples=120,random_state=SEED,
        n_jobs=4,verbosity=-1)
    m.fit(d.loc[train,FEATS],d.loc[train,"units_sold_observed"],
        eval_set=[(d.loc[valid,FEATS],d.loc[valid,"units_sold_observed"])],
        callbacks=[early_stopping(20,verbose=False)])
    return m

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--panel",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(args.panel) if args.panel.suffix.lower()==".csv" else pd.read_excel(args.panel)
    d["date"]=pd.to_datetime(d.date)
    d=build_features(d)
    train=d.date<"2025-08-01"
    valid=d.date.between("2025-08-01","2025-09-30")
    test=d.date>="2025-10-01"
    assert test.sum()==47104, "Unexpected test rows"
    y=d.loc[test,"units_sold_observed"].to_numpy()
    original=refit(d,train,valid)
    p={"seasonal_naive":d.loc[test,"lag_7"].to_numpy(),
       "trailing_mean":d.loc[test,"roll_7"].to_numpy(),
       "lightgbm":np.maximum(original.predict(d.loc[test,FEATS]),0)}
    binary=LGBMClassifier(n_estimators=220,learning_rate=.055,num_leaves=21,
         max_depth=6,min_child_samples=130,random_state=SEED,n_jobs=4,verbosity=-1)
    binary.fit(d.loc[train,FEATS],(d.loc[train,"units_sold_observed"]>0).astype(int))
    positive=train&(d.units_sold_observed>0)
    posm=LGBMRegressor(n_estimators=220,learning_rate=.055,num_leaves=21,
         max_depth=6,min_child_samples=80,random_state=SEED,n_jobs=4,verbosity=-1)
    posm.fit(d.loc[positive,FEATS],d.loc[positive,"units_sold_observed"])
    p["two_stage"]=binary.predict_proba(d.loc[test,FEATS])[:,1]*np.maximum(0,posm.predict(d.loc[test,FEATS]))
    try:
        from xgboost import XGBRegressor
        x=d[FEATS].copy()
        for c in ("shop_id","category"):x[c]=x[c].cat.codes.astype("int16")
        gb=XGBRegressor(n_estimators=260,max_depth=6,learning_rate=.055,
            subsample=.85,colsample_bytree=.9,tree_method="hist",random_state=SEED,n_jobs=4)
        gb.fit(x.loc[train],d.loc[train,"units_sold_observed"])
        p["xgboost"]=np.maximum(0,gb.predict(x.loc[test]))
    except ImportError:
        pass
    res={"historical_test_reused":True,"model_results":{k:score(y,v) for k,v in p.items()},
         "zero_observed_sales_fraction":float((y==0).mean()),
         "hierarchical_levels":{},"temporal_folds":[]}
    eval=d.loc[test,["date","shop_id","category","units_sold_observed"]].copy()
    eval["pred"]=p["lightgbm"];eval["error"]=eval.pred-eval.units_sold_observed
    for label,cols in [
        ("network_daily",["date"]),("shop_daily",["date","shop_id"]),
        ("category_daily",["date","category"]),
        ("shop_category_daily",["date","shop_id","category"])
    ]:
        g=eval.groupby(cols,observed=True)[["units_sold_observed","pred"]].sum()
        res["hierarchical_levels"][label]=score(g.units_sold_observed,g.pred)
    day=eval.groupby("date").error.sum()
    res["error_cancellation_fraction"]=float(1-np.abs(day).sum()/np.abs(eval.error).sum())
    pos=eval.units_sold_observed.gt(0);zero=~pos
    res["positive_sales_subset"]=score(eval.loc[pos,"units_sold_observed"],eval.loc[pos,"pred"])
    res["zero_sales_subset"]=score(eval.loc[zero,"units_sold_observed"],eval.loc[zero,"pred"])
    # WAPE is undefined for the zero-only subset; never report a fake very large ratio.
    for a,b,c in [("2025-01-01","2025-03-01","2025-04-01"),
                  ("2025-03-01","2025-05-01","2025-06-01"),
                  ("2025-05-01","2025-07-01","2025-08-01")]:
        tr=d.date<a;va=(d.date>=a)&(d.date<b);te=(d.date>=b)&(d.date<c)
        m=refit(d,tr,va,260)
        res["temporal_folds"].append(dict(test_from=b,test_before=c,
            lightgbm=score(d.loc[te,"units_sold_observed"],m.predict(d.loc[te,FEATS])),
            trailing_mean=score(d.loc[te,"units_sold_observed"],d.loc[te,"roll_7"])))
    items=res["hierarchical_levels"]
    plt.figure(figsize=(8,4.4))
    ks=list(items)
    vals=[items[k]["wape"]*100 for k in ks]
    plt.bar(["Network","Shop","Category","Shop-category"],vals)
    plt.ylabel("WAPE (%)");plt.title("Same forecasts at four levels");plt.tight_layout()
    plt.savefig(args.out/"rq1_hierarchy_wape.png",dpi=250,bbox_inches="tight");plt.close()
    series=eval.groupby(["shop_id","category"],observed=True).agg(
        actual=("units_sold_observed","sum"),
        zero_rate=("units_sold_observed",lambda x:(x==0).mean()),
        abs_err=("error",lambda x:np.abs(x).sum())).reset_index()
    series["wape"]=series.abs_err/series.actual.replace(0,np.nan)
    plt.figure(figsize=(7,4))
    plt.scatter(100*series.zero_rate,100*series.wape,alpha=.3,s=13)
    plt.xlabel("Observed zero-sales days (%)")
    plt.ylabel("Per-series WAPE (%)")
    plt.title("Sparsity association (not causal)")
    plt.tight_layout();plt.savefig(args.out/"rq1_zero_vs_error.png",dpi=250,bbox_inches="tight");plt.close()
    (args.out/"advanced_rq1_metrics.json").write_text(json.dumps(res,indent=2),encoding="utf-8")
    print(json.dumps({k:res[k] for k in ("hierarchical_levels","error_cancellation_fraction")},indent=2))
if __name__=="__main__":
    main()
