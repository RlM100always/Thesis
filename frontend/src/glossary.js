// One place where every technical term gets a business translation.
//
// The dashboard has two audiences: a shop owner who needs to know who to call
// this week, and a thesis examiner who needs the confidence intervals. Rather
// than picking one, every term carries both readings and the Simple/Technical
// toggle chooses which leads. Keeping them in one file is what stops the two
// vocabularies drifting apart across pages.
//
//   label  — the technical name, shown in Technical mode
//   plain  — what a business owner would call it, shown in Simple mode
//   detail — the one-sentence "why should I care", shown on expand in both

export const GLOSSARY = {
  accuracy: {
    label: "Accuracy",
    plain: "How often it gets the group right",
    detail: "Out of every 100 customers, this many are placed in the correct value group.",
  },
  f1_macro: {
    label: "F1-macro",
    plain: "Fairness across all groups",
    detail:
      "A single score that treats small groups as importantly as large ones, so a model cannot look good by only getting the biggest group right.",
  },
  ci: {
    label: "95% confidence interval",
    plain: "Realistic best and worst case",
    detail:
      "Test on a different sample of customers and the score would land somewhere in this range 19 times out of 20.",
  },
  cv: {
    label: "5-fold cross-validation",
    plain: "Re-tested on five different splits",
    detail:
      "The data was split five ways and the model retrained each time, so the score is not a lucky one-off.",
  },
  mcnemar: {
    label: "McNemar test",
    plain: "Is one model genuinely better?",
    detail:
      "Checks whether the gap between two models is real or just chance. Below 0.05 means real.",
  },
  roc_auc: {
    label: "ROC-AUC",
    plain: "Ability to tell the two groups apart",
    detail:
      "Pick one customer who left and one who stayed: this is how often the model scores the leaver higher. 0.5 is a coin flip, 1.0 is perfect.",
  },
  pr_auc: {
    label: "PR-AUC",
    plain: "Accuracy on the rare cases",
    detail:
      "Focuses on the small group you actually care about, so a model cannot score well by saying 'no' to everyone.",
  },
  lift: {
    label: "Lift @ 10%",
    plain: "Payoff from targeting the top 10%",
    detail:
      "Contact the 10% the model flags first and you reach this many times more real leavers than picking 10% at random.",
  },
  rmse: {
    label: "RMSE",
    plain: "Typical forecast error (large misses hurt more)",
    detail: "Average size of the miss in taka, with big misses weighted heavily. Lower is better.",
  },
  mae: {
    label: "MAE",
    plain: "Typical forecast error in taka",
    detail: "On an average month, the forecast is off by about this much. Lower is better.",
  },
  mape: {
    label: "MAPE",
    plain: "Typical forecast error as a percentage",
    detail: "How far off the forecast is in percentage terms. Under 10% is usually good enough to plan with.",
  },
  silhouette: {
    label: "Silhouette score",
    plain: "How cleanly the groups separate",
    detail:
      "Near 1 means tight, well-separated groups; near 0 means the groups blur into each other. This dataset scores low, so treat the groups as a rough guide.",
  },
  shap: {
    label: "SHAP contribution",
    plain: "What pushed this customer's score",
    detail:
      "Each bar shows how much one fact about the customer moved the prediction up or down.",
  },
  recency: {
    label: "Recency",
    plain: "Days since last purchase",
    detail: "The longer the gap, the more likely the customer has drifted away.",
  },
  frequency: {
    label: "Frequency",
    plain: "Purchases per month",
    detail: "How often this customer buys, on average.",
  },
  monetary: {
    label: "Monetary",
    plain: "Total spent",
    detail: "Everything this customer has spent with you, added up.",
  },
  leakage: {
    label: "Leakage ablation",
    plain: "Proof the high score was fake",
    detail:
      "The same model run with and without a field that secretly gave away the answer. The gap is how much of the original score was an illusion.",
  },
  base_rate: {
    label: "Base rate",
    plain: "How common it is to begin with",
    detail: "What you would get by guessing. Any model has to beat this to be worth anything.",
  },
};

export function term(key) {
  return GLOSSARY[key] ?? { label: key, plain: key, detail: "" };
}
