"""Random Forest on the German Credit dataset: WITHOUT vs WITH hyperparameter tuning.

Dataset: German Credit (OpenML "credit-g", version 1), downloaded by scikit-learn
on first run and cached in ./openml_cache. 1000 loan applicants, 20 features
(7 numeric, 13 categorical), target = credit risk: good (700) / bad (300).
"bad" is treated as the positive class, since catching bad loans is the goal.

Steps:
1. One-hot encode the categorical columns.
2. Split data 80% train / 20% test (stratified, fixed seed).
3. Model A: RandomForestClassifier with default settings.
4. Model B: same model, hyperparameters chosen by GridSearchCV
   (5-fold cross-validation on the TRAIN set only, scoring = F1 for "bad").
5. Evaluate both on the same untouched test set and print a comparison table.

Run:  python random_forest_credit.py
"""

import time

import pandas as pd
from sklearn.datasets import fetch_openml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score, train_test_split

SEED = 42

data = fetch_openml("credit-g", version=1, as_frame=True, data_home="openml_cache")
X = pd.get_dummies(data.data, dtype=int)
y = (data.target == "bad").astype(int)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=SEED
)
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)


def evaluate(name, model, train_time):
    pred = model.predict(X_test)
    prob = model.predict_proba(X_test)[:, 1]
    cv_f1 = cross_val_score(model, X_train, y_train, cv=cv, scoring="f1").mean()
    print(f"\nConfusion matrix ({name}), rows = actual [good, bad]:\n{confusion_matrix(y_test, pred)}")
    return {
        "Model": name,
        "CV F1 (train, 5-fold)": cv_f1,
        "Test Accuracy": accuracy_score(y_test, pred),
        "Test Precision (bad)": precision_score(y_test, pred),
        "Test Recall (bad)": recall_score(y_test, pred),
        "Test F1 (bad)": f1_score(y_test, pred),
        "Test ROC-AUC": roc_auc_score(y_test, prob),
        "Fit time (s)": train_time,
    }


# ---- Model A: without hyperparameter tuning (defaults) ----
default_rf = RandomForestClassifier(random_state=SEED)
start = time.perf_counter()
default_rf.fit(X_train, y_train)
default_time = time.perf_counter() - start

# ---- Model B: with hyperparameter tuning (GridSearchCV) ----
param_grid = {
    "n_estimators": [100, 300],
    "max_depth": [None, 5, 10],
    "min_samples_leaf": [1, 3, 5],
    "max_features": ["sqrt", "log2"],
    "class_weight": [None, "balanced"],
}
search = GridSearchCV(
    RandomForestClassifier(random_state=SEED),
    param_grid,
    scoring="f1",
    cv=cv,
    n_jobs=-1,
)
start = time.perf_counter()
search.fit(X_train, y_train)
tuned_time = time.perf_counter() - start
tuned_rf = search.best_estimator_

print("Dataset:", X.shape[0], "rows,", data.data.shape[1], "features ->", X.shape[1],
      "after one-hot | train", len(y_train), "/ test", len(y_test))
print("Default hyperparameters:",
      {k: default_rf.get_params()[k] for k in param_grid})
print("Best hyperparameters   :", search.best_params_)
print("Combinations tried     :", len(search.cv_results_["params"]), "x 5 folds")

results = pd.DataFrame([
    evaluate("Without tuning (default)", default_rf, default_time),
    evaluate("With tuning (GridSearchCV)", tuned_rf, tuned_time),
]).set_index("Model")

pd.set_option("display.width", 200)
print("\n=== Comparison on the same test set ===")
print(results.T.round(4))
results.round(4).to_csv("random_forest_credit_results.csv")
print("\nSaved: random_forest_credit_results.csv")
