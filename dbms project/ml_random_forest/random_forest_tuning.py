"""Random Forest: results WITHOUT vs WITH hyperparameter tuning.

Dataset: Breast Cancer Wisconsin (built into scikit-learn, 569 rows, 30 features,
2 classes: malignant / benign). No download needed.

Steps:
1. Split data 80% train / 20% test (stratified, fixed seed).
2. Model A: RandomForestClassifier with default settings.
3. Model B: same model, hyperparameters chosen by GridSearchCV
   (5-fold cross-validation on the TRAIN set only, scoring = F1).
4. Evaluate both on the same untouched test set and print a comparison table.

Run:  python random_forest_tuning.py
"""

import time

import pandas as pd
from sklearn.datasets import load_breast_cancer
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

data = load_breast_cancer()
X, y = data.data, data.target
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=SEED
)
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)


def evaluate(name, model, train_time):
    pred = model.predict(X_test)
    prob = model.predict_proba(X_test)[:, 1]
    cv_f1 = cross_val_score(model, X_train, y_train, cv=cv, scoring="f1").mean()
    print(f"\nConfusion matrix ({name}):\n{confusion_matrix(y_test, pred)}")
    return {
        "Model": name,
        "CV F1 (train, 5-fold)": cv_f1,
        "Test Accuracy": accuracy_score(y_test, pred),
        "Test Precision": precision_score(y_test, pred),
        "Test Recall": recall_score(y_test, pred),
        "Test F1": f1_score(y_test, pred),
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
    "n_estimators": [100, 200, 400],
    "max_depth": [None, 5, 10],
    "min_samples_split": [2, 5],
    "min_samples_leaf": [1, 2, 4],
    "max_features": ["sqrt", "log2"],
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

print("Dataset:", X.shape[0], "rows,", X.shape[1], "features | train", len(y_train), "/ test", len(y_test))
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
results.round(4).to_csv("random_forest_results.csv")
print("\nSaved: random_forest_results.csv")
