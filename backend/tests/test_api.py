import unittest
import pandas as pd
from pathlib import Path
from fastapi.testclient import TestClient
from app import app


class APITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("PlannerAgent", data["agents"])

    def test_samples_list(self):
        response = self.client.get("/api/samples")
        self.assertEqual(response.status_code, 200)
        samples = response.json()
        self.assertGreaterEqual(len(samples), 3)
        ids = [s["id"] for s in samples]
        self.assertIn("churn", ids)
        self.assertIn("housing", ids)
        self.assertIn("sales", ids)

    def test_analyze_sample(self):
        response = self.client.post(
            "/api/analyze",
            data={"sample_id": "churn", "inquiry": "Predict customer churn"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("plan", data)
        self.assertEqual(data["plan"]["problem_type"], "classification")
        self.assertIn("critic", data)
        self.assertIn("score", data["critic"])
        self.assertIn("models", data)
        self.assertGreaterEqual(len(data["models"]), 1)

    def test_tool_catalogue_and_allowlist(self):
        catalogue = self.client.get("/api/tools")
        self.assertEqual(catalogue.status_code, 200)
        names = [tool["name"] for tool in catalogue.json()["tools"]]
        self.assertIn("dataset.profile", names)
        allowed = self.client.post("/api/tools/call", json={"name": "dataset.profile", "arguments": {"target_column": "churn"}})
        self.assertEqual(allowed.status_code, 200)
        denied = self.client.post("/api/tools/call", json={"name": "execute.shell", "arguments": {}})
        self.assertEqual(denied.status_code, 403)

    def test_history_endpoint(self):
        self.client.post("/api/analyze", data={"sample_id": "churn", "inquiry": "Predict churn"})
        response = self.client.get("/api/history")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()["items"]), 1)

    def test_analyze_custom_csv(self):
        csv_rows = ["area,rooms,price"]
        for i in range(30):
            area = 1000 + i * 50
            rooms = 2 + (i % 4)
            price = 150000 + area * 120 + rooms * 15000
            csv_rows.append(f"{area},{rooms},{price}")
        csv_content = "\n".join(csv_rows)

        files = {"file": ("test_houses.csv", csv_content, "text/csv")}
        response = self.client.post(
            "/api/analyze",
            files=files,
            data={"inquiry": "Estimate house sale prices based on area and rooms", "target_column": "price"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["plan"]["problem_type"], "regression")
        self.assertEqual(data["plan"]["target_column"], "price")
        self.assertIn("critic", data)

    def test_reporting_status_does_not_expose_secrets(self):
        response = self.client.get("/api/reporting/status")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("api_key", response.json())

    def test_async_analysis_job_endpoint(self):
        response = self.client.post("/api/analysis/start", data={"sample_id":"housing", "inquiry":"Estimate house price", "target_column":"price", "problem_type":"regression"})
        self.assertEqual(response.status_code, 202)
        job_id = response.json()["job_id"]
        job = self.client.get(f"/api/analysis/{job_id}")
        self.assertEqual(job.status_code, 200)
        self.assertIn(job.json()["status"], {"completed", "running", "queued"})
        if job.json()["status"] == "completed":
            self.assertIn("report", job.json()["result"])

    def test_upload_rejects_unsupported_file_type(self):
        response = self.client.post("/api/profile", files={"file": ("payload.exe", b"not a dataset", "application/octet-stream")})
        self.assertEqual(response.status_code, 415)

    def test_report_pdf_download(self):
        response = self.client.post("/api/analyze", data={"sample_id":"housing", "inquiry":"Estimate house price", "target_column":"price", "problem_type":"regression"})
        self.assertEqual(response.status_code, 200)
        experiment_id = response.json()["experiment_id"]
        pdf = self.client.get(f"/api/history/{experiment_id}/report.pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers.get("content-type"), "application/pdf")

    def test_saved_model_prediction_endpoint(self):
        analysis = self.client.post("/api/analyze", data={"sample_id":"housing", "inquiry":"Estimate house price", "target_column":"price", "problem_type":"regression"})
        self.assertEqual(analysis.status_code, 200)
        artifact_id = analysis.json().get("artifact", {}).get("artifact_id")
        self.assertTrue(artifact_id)
        csv_content = "square_feet,bedrooms,bathrooms,age_years,garage_cars,location_score\n1500,3,2,10,2,7.5\n2000,4,2.5,5,2,8.5"
        prediction = self.client.post(f"/api/models/{artifact_id}/predict", files={"file": ("new_houses.csv", csv_content, "text/csv")})
        self.assertEqual(prediction.status_code, 200, prediction.text)
        self.assertEqual(prediction.json()["rows"], 2)

    def test_saved_report_can_be_regenerated(self):
        response = self.client.post("/api/analyze", data={"sample_id":"housing", "inquiry":"Estimate house price", "target_column":"price", "problem_type":"regression"})
        experiment_id = response.json()["experiment_id"]
        regenerated = self.client.post(f"/api/history/{experiment_id}/report/regenerate")
        self.assertEqual(regenerated.status_code, 200)
        self.assertIn(regenerated.json()["report"]["llm"]["status"], {"not_configured", "used", "failed_fallback"})
        saved = self.client.get(f"/api/history/{experiment_id}").json()
        self.assertEqual(saved["dataset_name"], "housing")

    def test_classification_artifact_preserves_original_target_labels(self):
        analysis = self.client.post("/api/analyze", data={"sample_id":"churn", "inquiry":"Predict customer churn", "target_column":"churn", "problem_type":"classification"})
        self.assertEqual(analysis.status_code, 200)
        artifact_id = analysis.json().get("artifact", {}).get("artifact_id")
        self.assertTrue(artifact_id)
        source = pd.read_csv(Path(__file__).resolve().parents[1] / "sample_data" / "customer_churn.csv")
        features = source.drop(columns=["churn"]).head(2)
        payload = features.to_csv(index=False)
        response = self.client.post(f"/api/models/{artifact_id}/predict", files={"file": ("new_customers.csv", payload, "text/csv")})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(response.json()["predictions"][0]["prediction"].lower(), {"yes", "no"})


if __name__ == "__main__":
    unittest.main()
