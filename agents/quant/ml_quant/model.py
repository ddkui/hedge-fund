import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from collections import Counter


class MLEnsemble:
    def __init__(self):
        self.scaler = StandardScaler()
        self.models = [
            LogisticRegression(max_iter=500, random_state=42),
            RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42),
            GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42),
        ]
        self.trained = False

    def fit(self, X: np.ndarray, y: np.ndarray):
        X_scaled = self.scaler.fit_transform(X)
        for model in self.models:
            model.fit(X_scaled, y)
        self.trained = True

    def predict(self, X: np.ndarray) -> tuple[int, float]:
        if not self.trained:
            return 0, 0.5
        X_scaled = self.scaler.transform(X)
        votes = []
        probs = []
        for model in self.models:
            pred = int(model.predict(X_scaled)[0])
            prob = float(np.max(model.predict_proba(X_scaled)[0]))
            votes.append(pred)
            probs.append(prob)
        direction = Counter(votes).most_common(1)[0][0]
        confidence = float(np.mean(probs))
        return direction, confidence
