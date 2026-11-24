import unittest
import pandas as pd
from data_pilot.profiler import profile_dataframe


class ProfilerTests(unittest.TestCase):
    def test_profiles_dataframe_correctly(self):
        data = {
            "age": [25, 30, 35, 40, None],
            "churn": ["Yes", "No", "No", "No", "Yes"],
            "income": [50000.0, 60000.0, 75000.0, 80000.0, 95000.0],
            "active": [True, False, True, True, False],
        }
        df = pd.DataFrame(data)
        profile = profile_dataframe(df, target_column="churn")

        self.assertEqual(profile.rows, 5)
        self.assertEqual(len(profile.columns), 4)

        age_col = profile.column("age")
        self.assertIsNotNone(age_col)
        self.assertEqual(age_col.kind, "numeric")
        self.assertEqual(age_col.missing_count, 1)

        churn_col = profile.column("churn")
        self.assertIsNotNone(churn_col)
        self.assertEqual(churn_col.kind, "categorical")
        self.assertEqual(churn_col.unique_count, 2)

        active_col = profile.column("active")
        self.assertIsNotNone(active_col)
        self.assertEqual(active_col.kind, "boolean")

        self.assertEqual(profile.potential_target_columns, ("churn",))
        self.assertIsNotNone(profile.class_imbalance_ratio)


if __name__ == "__main__":
    unittest.main()
