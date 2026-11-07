#!/usr/bin/env python3
"""Privacy-conscious offline RQ2 model attribution, not human usability evidence."""
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd,joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshots",type=Path,required=True)
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    c=pd.read_csv(a.snapshots) if a.snapshots.suffix.lower()==".csv" else pd.read_excel(a.snapshots)
    pack=joblib.load(a.model)
    test=c[c.split.astype(str).str.upper()=="TEST"].sample(n=1200,random_state=42)
    X=pd.get_dummies(test[pack["features"]],columns=["home_shop_id"],dtype=np.int8)
    X=X.reindex(columns=pack["dummy_columns"],fill_value=0)
    X=X.fillna(pack["dummy_median"])
    contrib=pack["lightgbm"].predict(X,pred_contrib=True)
    assert contrib.shape[1]==len(pack["dummy_columns"])+1
    scores=pd.DataFrame({"feature":pack["dummy_columns"],
        "mean_abs_logit_shap":np.abs(contrib[:,:-1]).mean(axis=0)})
    scores=scores.sort_values("mean_abs_logit_shap",ascending=False)
    scores.to_csv(a.out/"rq2_shap_global_aggregate.csv",index=False)
    q=scores.head(12).sort_values("mean_abs_logit_shap")
    fig,ax=plt.subplots(figsize=(9,5))
    ax.barh(q.feature,q.mean_abs_logit_shap)
    ax.set_xlabel("Mean absolute TreeSHAP contribution (raw log-odds)")
    ax.set_title("B-SMART RQ2: test-sample attribution, no causal claim")
    fig.tight_layout();fig.savefig(a.out/"rq2_shap_global.png",dpi=250,bbox_inches="tight")
    plt.close(fig)
    (a.out/"rq2_shap_metadata.json").write_text(json.dumps({
        "sample_rows":1200,
        "method":"LightGBM native pred_contrib / TreeSHAP",
        "scale":"raw-score log-odds",
        "warning":"Associational model attribution, not human validation or causal effect",
        "top_features":scores.head(8).to_dict("records")
    },indent=2),encoding="utf-8")
if __name__=="__main__":main()
