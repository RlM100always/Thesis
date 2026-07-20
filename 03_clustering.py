"""
=============================================================
STEP 3: CUSTOMER SEGMENTATION — K-Means Clustering
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
TASK: Segment 4,996 unique customers using RFM features

HOW TO RUN (after step 1):
    python 03_clustering.py

WHAT THIS GENERATES (output/figures/):
  - elbow_curve.png          → optimal K selection
  - silhouette_scores.png    → cluster quality
  - kmeans_clusters_2d.png   → 2D PCA scatter plot
  - rfm_cluster_heatmap.png  → cluster profile heatmap
  - cluster_distribution.png → pie chart of segments
"""

import pandas as pd
import numpy as np
import pickle
import os
import warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

warnings.filterwarnings("ignore")
os.makedirs("output/figures", exist_ok=True)
os.makedirs("output/models", exist_ok=True)

print("=" * 60)
print("  STEP 3: K-MEANS CUSTOMER SEGMENTATION")
print("=" * 60)

# ─────────────────────────────────────────────
# 1. LOAD PROCESSED DATA
# ─────────────────────────────────────────────
print("\n[1] Loading processed dataset...")
df = pd.read_csv("output/processed_dataset.csv")
print(f"    Total records: {len(df):,}")

# ─────────────────────────────────────────────
# 2. BUILD RFM CUSTOMER-LEVEL AGGREGATION
# ─────────────────────────────────────────────
print("\n[2] Building RFM Customer Profile...")

customer_rfm = df.groupby("Customer_ID").agg(
    Recency  = ("Days_Since_Last_Purchase", "min"),        # Lower = better
    Frequency= ("Purchase_Frequency_Monthly", "mean"),
    Monetary = ("Net_Amount_BDT", "sum"),
    CLV      = ("Customer_Lifetime_Value_BDT", "first"),
    Avg_CSAT = ("Customer_Satisfaction_Score", "mean"),
    Txn_Count= ("Transaction_ID", "count"),
    Avg_Disc = ("Discount_Percent", "mean"),
    Ret_Rate = ("Return_Binary", "mean"),
).reset_index()

print(f"    Unique customers: {len(customer_rfm):,}")
print(f"    RFM Features: Recency, Frequency, Monetary, CLV, CSAT, Txn_Count, Avg_Discount, Return_Rate")

# ─────────────────────────────────────────────
# 3. SCALE RFM FEATURES
# ─────────────────────────────────────────────
rfm_features = ["Recency", "Frequency", "Monetary", "CLV", "Avg_CSAT", "Txn_Count", "Avg_Disc"]
X_rfm = customer_rfm[rfm_features].values
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_rfm)
print("\n[3] Features standardized (StandardScaler)")

# ─────────────────────────────────────────────
# 4. ELBOW METHOD — Find Optimal K
# ─────────────────────────────────────────────
print("\n[4] Running Elbow Method (K = 2 to 10)...")
inertias, sil_scores = [], []
K_range = range(2, 11)

for k in K_range:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)
    inertias.append(km.inertia_)
    sil_scores.append(silhouette_score(X_scaled, labels))
    print(f"    K={k}: Inertia={km.inertia_:.0f}, Silhouette={sil_scores[-1]:.4f}")

# Plot Elbow Curve
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].plot(list(K_range), inertias, "bo-", linewidth=2, markersize=8)
axes[0].axvline(x=4, color="red", linestyle="--", alpha=0.7, label="Optimal K=4")
axes[0].set_title("Elbow Method — Inertia vs K", fontsize=13, fontweight="bold")
axes[0].set_xlabel("Number of Clusters (K)", fontsize=11)
axes[0].set_ylabel("Inertia (WCSS)", fontsize=11)
axes[0].legend()
axes[0].grid(alpha=0.3)
axes[0].spines[["top","right"]].set_visible(False)

axes[1].plot(list(K_range), sil_scores, "gs-", linewidth=2, markersize=8)
axes[1].axvline(x=4, color="red", linestyle="--", alpha=0.7, label="Optimal K=4")
axes[1].set_title("Silhouette Score vs K", fontsize=13, fontweight="bold")
axes[1].set_xlabel("Number of Clusters (K)", fontsize=11)
axes[1].set_ylabel("Silhouette Score", fontsize=11)
axes[1].legend()
axes[1].grid(alpha=0.3)
axes[1].spines[["top","right"]].set_visible(False)

plt.tight_layout()
plt.savefig("output/figures/elbow_silhouette.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/elbow_silhouette.png")

# ─────────────────────────────────────────────
# 5. FINAL K-MEANS WITH K=4
# ─────────────────────────────────────────────
print("\n[5] Training Final K-Means with K=4...")
OPTIMAL_K = 4
kmeans = KMeans(n_clusters=OPTIMAL_K, random_state=42, n_init=15)
customer_rfm["Cluster"] = kmeans.fit_predict(X_scaled)
final_sil = silhouette_score(X_scaled, customer_rfm["Cluster"])
print(f"    Final Silhouette Score: {final_sil:.4f}")
print(f"    Cluster Distribution:\n{customer_rfm['Cluster'].value_counts().sort_index().to_string()}")

# ─────────────────────────────────────────────
# 6. LABEL CLUSTERS BY BEHAVIOR
# ─────────────────────────────────────────────
print("\n[6] Labeling Clusters by RFM Profile...")
cluster_profile = customer_rfm.groupby("Cluster")[rfm_features].mean()
print(cluster_profile.round(2).to_string())

# Sort by Monetary descending → assign labels accordingly
monetary_order = cluster_profile["Monetary"].rank(ascending=False)
cluster_labels = {}
for c in range(OPTIMAL_K):
    rank = monetary_order[c]
    if rank == 1:
        cluster_labels[c] = "VIP-Platinum"
    elif rank == 2:
        cluster_labels[c] = "High-Value"
    elif rank == 3:
        cluster_labels[c] = "Moderate-Spender"
    else:
        cluster_labels[c] = "Low-Engagement"

customer_rfm["Segment"] = customer_rfm["Cluster"].map(cluster_labels)
print(f"\n    Cluster → Segment mapping: {cluster_labels}")
print(f"\n    Segment Counts:\n{customer_rfm['Segment'].value_counts().to_string()}")

# ─────────────────────────────────────────────
# 7. PCA 2D SCATTER PLOT
# ─────────────────────────────────────────────
print("\n[7] PCA 2D Visualization...")
pca = PCA(n_components=2, random_state=42)
X_pca = pca.fit_transform(X_scaled)
explained = pca.explained_variance_ratio_

COLORS = {"VIP-Platinum": "#F5A623", "High-Value": "#0A8754", "Moderate-Spender": "#1565C0", "Low-Engagement": "#E63946"}

fig, ax = plt.subplots(figsize=(9, 6))
for seg, color in COLORS.items():
    mask = customer_rfm["Segment"] == seg
    ax.scatter(X_pca[mask, 0], X_pca[mask, 1], c=color, label=seg, alpha=0.6, s=35, edgecolors="white", linewidth=0.3)

ax.set_title(f"K-Means Clusters — 2D PCA Projection\n(PC1={explained[0]*100:.1f}% + PC2={explained[1]*100:.1f}% = {sum(explained)*100:.1f}% variance explained)", fontsize=12, fontweight="bold")
ax.set_xlabel(f"Principal Component 1 ({explained[0]*100:.1f}%)", fontsize=11)
ax.set_ylabel(f"Principal Component 2 ({explained[1]*100:.1f}%)", fontsize=11)
ax.legend(fontsize=10, framealpha=0.9)
ax.grid(alpha=0.2)
ax.spines[["top","right"]].set_visible(False)
plt.tight_layout()
plt.savefig("output/figures/kmeans_clusters_2d.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/kmeans_clusters_2d.png")

# ─────────────────────────────────────────────
# 8. CLUSTER PROFILE HEATMAP
# ─────────────────────────────────────────────
print("\n[8] Cluster Profile Heatmap...")
seg_order = ["VIP-Platinum", "High-Value", "Moderate-Spender", "Low-Engagement"]
profile_by_seg = customer_rfm.groupby("Segment")[rfm_features].mean().reindex(seg_order)
profile_norm = (profile_by_seg - profile_by_seg.min()) / (profile_by_seg.max() - profile_by_seg.min() + 1e-9)

fig, ax = plt.subplots(figsize=(10, 4))
sns.heatmap(
    profile_norm, annot=profile_by_seg.round(1), fmt=".1f",
    cmap="YlOrRd", linewidths=0.5, linecolor="gray",
    ax=ax, cbar_kws={"label": "Normalized Score"}
)
ax.set_title("Customer Segment Profile Heatmap (RFM Features)", fontsize=13, fontweight="bold")
ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=10)
ax.set_xticklabels([f.replace("_", " ") for f in rfm_features], rotation=25, ha="right", fontsize=9)
plt.tight_layout()
plt.savefig("output/figures/rfm_cluster_heatmap.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/rfm_cluster_heatmap.png")

# ─────────────────────────────────────────────
# 9. SEGMENT PIE CHART
# ─────────────────────────────────────────────
seg_counts = customer_rfm["Segment"].value_counts().reindex(seg_order)
fig, ax = plt.subplots(figsize=(7, 6))
wedge_colors = ["#F5A623", "#0A8754", "#1565C0", "#E63946"]
wedges, texts, autotexts = ax.pie(
    seg_counts, labels=seg_counts.index, autopct="%1.1f%%",
    colors=wedge_colors, startangle=140,
    wedgeprops=dict(edgecolor="white", linewidth=2),
    textprops=dict(fontsize=11),
)
for at in autotexts:
    at.set_fontsize(11)
    at.set_fontweight("bold")
    at.set_color("white")
ax.set_title("Customer Segment Distribution\n(K-Means, K=4)", fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig("output/figures/cluster_distribution.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/cluster_distribution.png")

# Save model & results
with open("output/models/kmeans_model.pkl", "wb") as f:
    pickle.dump(kmeans, f)
customer_rfm.to_csv("output/customer_segments.csv", index=False)
print("    → Saved: output/models/kmeans_model.pkl")
print("    → Saved: output/customer_segments.csv")

print("\n" + "=" * 60)
print("  ✅ K-MEANS CLUSTERING COMPLETE")
print(f"  Silhouette Score: {final_sil:.4f} (closer to 1.0 = better)")
print("  Next: Run  python 04_forecasting.py")
print("=" * 60)
