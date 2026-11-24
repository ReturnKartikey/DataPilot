"""Small CPU-capable PyTorch MLP estimators with sklearn-compatible APIs."""
from __future__ import annotations
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin

class _TorchMLP(BaseEstimator):
    def __init__(self, hidden_size=64, epochs=80, learning_rate=0.001, dropout=0.15, batch_size=64, random_state=42, patience=10):
        self.hidden_size=hidden_size; self.epochs=epochs; self.learning_rate=learning_rate
        self.dropout=dropout; self.batch_size=batch_size; self.random_state=random_state; self.patience=patience
    def _fit(self, X, y, classification):
        try: import torch
        except ImportError as exc: raise ImportError("PyTorch is optional. Install with: pip install torch") from exc
        from torch import nn
        torch.manual_seed(self.random_state); np.random.seed(self.random_state)
        Xn=np.asarray(X,dtype=np.float32); Xn=np.nan_to_num(Xn,nan=0.0,posinf=0.0,neginf=0.0)
        self.n_features_in_=Xn.shape[1]
        if classification:
            self.classes_, yi=np.unique(y,return_inverse=True); out=max(2,len(self.classes_)); target=torch.tensor(yi,dtype=torch.long)
            loss_fn=nn.CrossEntropyLoss()
        else:
            out=1; target=torch.tensor(np.asarray(y,dtype=np.float32).reshape(-1,1)); loss_fn=nn.MSELoss()
        self.model_=nn.Sequential(nn.Linear(self.n_features_in_,self.hidden_size),nn.ReLU(),nn.BatchNorm1d(self.hidden_size),nn.Dropout(self.dropout),nn.Linear(self.hidden_size,max(16,self.hidden_size//2)),nn.ReLU(),nn.Linear(max(16,self.hidden_size//2),out))
        opt=torch.optim.AdamW(self.model_.parameters(),lr=self.learning_rate,weight_decay=1e-4)
        x=torch.tensor(Xn)
        # Reserve a deterministic slice of the training fold for early stopping.
        permutation=torch.randperm(len(x))
        val_count=max(1,int(len(x)*0.15)) if len(x)>=12 else 0
        if val_count:
            val_ix=permutation[:val_count]; fit_ix=permutation[val_count:]
            x_fit,y_fit=x[fit_ix],target[fit_ix]
            x_val,y_val=x[val_ix],target[val_ix]
        else:
            x_fit,y_fit=x,target; x_val,y_val=x,target
        best=float("inf"); best_state=None; stale=0
        for epoch in range(self.epochs):
            self.model_.train()
            order=torch.randperm(len(x_fit))
            for start in range(0,len(x_fit),self.batch_size):
                ix=order[start:start+self.batch_size]
                if len(ix)<2: continue
                opt.zero_grad(); pred=self.model_(x_fit[ix]); loss=loss_fn(pred,y_fit[ix]); loss.backward(); opt.step()
            self.model_.eval()
            with torch.no_grad(): score=float(loss_fn(self.model_(x_val),y_val).item())
            if score < best-1e-6:
                best=score; best_state={k:v.detach().clone() for k,v in self.model_.state_dict().items()}; stale=0
            else: stale+=1
            if stale>=self.patience: break
        if best_state: self.model_.load_state_dict(best_state)
        self.model_.eval(); self.n_iter_=epoch+1
        return self
    def _predict(self,X):
        import torch
        Xn=np.asarray(X,dtype=np.float32); Xn=np.nan_to_num(Xn,nan=0.0,posinf=0.0,neginf=0.0)
        if Xn.shape[1]!=self.n_features_in_: raise ValueError("Feature count differs from fitted MLP")
        with torch.no_grad(): return self.model_(torch.tensor(Xn)).cpu().numpy()

class TabularMLPClassifier(ClassifierMixin, _TorchMLP):
    def fit(self,X,y): return self._fit(X,y,True)
    def predict(self,X): return self.classes_[self._predict(X).argmax(axis=1)]
    def predict_proba(self,X):
        import torch
        return torch.softmax(torch.tensor(self._predict(X)),dim=1).numpy()

class TabularMLPRegressor(RegressorMixin, _TorchMLP):
    def fit(self,X,y): return self._fit(X,y,False)
    def predict(self,X): return self._predict(X).reshape(-1)
