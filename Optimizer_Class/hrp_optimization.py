import pandas as pd
import numpy as np
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from scipy.spatial.distance import squareform
import matplotlib.pyplot as plt

class ClusterNode:
    def __init__(self, left=None, right=None, asset=None):
        self.left = left
        self.right = right
        self.asset = asset #getting the asset from the root gives u leaves

def get_assets(node):
    if node.left is None and node.right is None:
        return [node.asset]
    left = get_assets(node.left)
    right = get_assets(node.right)
    return (left + right)

def print_tree(node, level=0):
    if node is None:
        return
    print("  " * level, end="")
    if node.asset:
        print(node.asset) #node only has asset if its a leaf
    else:
        print("Cluster")
    print_tree(node.left, level + 1)
    print_tree(node.right, level + 1)

def get_linkage_matrix(corr: pd.DataFrame, method: str = "ward", plot: bool = False):
    #clip guards against tiny floating-point overshoot (corr slightly > 1 -> sqrt of a negative)
    distance = np.sqrt(np.clip((1-corr) / 2, 0, None))
    linkage_matrix = linkage(squareform(distance.values, checks=False), method=method)

    #visualization
    if plot:
        plt.figure(figsize=(10,6))
        dendrogram(linkage_matrix, labels=corr.columns.tolist())
        plt.show()
    return linkage_matrix

def build_tree(linkage_matrix, asset_names):
    # Step 1: create leaf nodes
    nodes = {}
    for i, asset in enumerate(asset_names):
        nodes[i] = ClusterNode(asset=asset)

    n_assets = len(asset_names)

    # Step 2: process each merge
    for i, row in enumerate(linkage_matrix):

        left_id = int(row[0])
        right_id = int(row[1])

        left_node = nodes[left_id]
        right_node = nodes[right_id]

        new_node = ClusterNode(
            left=left_node,
            right=right_node
        )
        cluster_id = n_assets + i
        nodes[cluster_id] = new_node

    # Step 3: last cluster is the root
    root = nodes[max(nodes.keys())]
    return root
#using covariance submatrix
def calculate_cluster_variance(cov, assets):
    sub_cov = cov.loc[assets, assets].values
    inverse_var = 1/np.diag(sub_cov)
    inverse_var /= inverse_var.sum()
    #inverse-variance weights within the cluster (canonical HRP)
    cluster_var = inverse_var.T @ sub_cov @ inverse_var
    return cluster_var

#when you start at the root the parent holds the entire weight as 1
def hrp_optimization(node, parent_weight, cov_matrix, weights):
    if node.asset is not None:
        #after every recursive call you are getting a fraction of the weight
        weights[node.asset] = parent_weight
        return
    left = calculate_cluster_variance(cov_matrix, get_assets(node.left))
    right = calculate_cluster_variance(cov_matrix, get_assets(node.right))
    alpha = 1 - left/(left+right)
    left_weight = parent_weight * alpha
    right_weight = parent_weight * (1-alpha)
    hrp_optimization(node.left, left_weight, cov_matrix, weights)
    hrp_optimization(node.right, right_weight, cov_matrix, weights)
    return weights

#derive the correlation matrix from a covariance matrix (clustering uses corr, bisection uses cov)
def cov_to_corr(cov: pd.DataFrame) -> pd.DataFrame:
    std = np.sqrt(np.diag(cov.values))
    corr = cov.values / np.outer(std, std)
    return pd.DataFrame(corr, index=cov.index, columns=cov.columns)

#driver: pass in the (already shrunk) covariance matrix; ties the three HRP stages together
def hrp_allocate(cov: pd.DataFrame, method: str = "ward", plot: bool = False) -> pd.Series:
    corr = cov_to_corr(cov)
    linkage_matrix = get_linkage_matrix(corr, method=method, plot=plot)
    root = build_tree(linkage_matrix, list(cov.columns))
    weights = {}
    hrp_optimization(root, 1.0, cov, weights)
    return pd.Series(weights)

#cut the HRP tree into k clusters, take the name HRP weights highest in each
#cluster (one per cluster -> k distinct risk groups), then re-run HRP on those k
def hrp_core4(cov: pd.DataFrame, k: int = 4, method: str = "ward", plot: bool = False) -> pd.Series:
    full_w = hrp_allocate(cov, method=method, plot=False)   # HRP weights over all names
    corr = cov_to_corr(cov)
    linkage_matrix = get_linkage_matrix(corr, method=method, plot=plot)
    labels = fcluster(linkage_matrix, t=k, criterion="maxclust")   # k clusters
    cluster_of = dict(zip(cov.columns, labels))

    # one representative per cluster: the name HRP itself weighted most in it
    reps = []
    for c in sorted(set(labels)):
        members = [a for a in cov.columns if cluster_of[a] == c]
        reps.append(max(members, key=lambda a: full_w[a]))

    # if the tree yielded < k clusters, top up by next-highest HRP weight
    if len(reps) < k:
        extra = [a for a in full_w.sort_values(ascending=False).index if a not in reps]
        reps += extra[: k - len(reps)]

    # re-run HRP on just the k representatives — renormalizes to 1 automatically
    sub_cov = cov.loc[reps, reps]
    return hrp_allocate(sub_cov, method=method, plot=False).sort_values(ascending=False)
