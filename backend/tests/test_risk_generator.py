import unittest

from data_pilot.agents import (
    ColumnProfile,
    DatasetProfile,
    Objective,
    PlannerAgent,
    RiskTrajectoryGenerator,
)


class RiskTrajectoryGeneratorTests(unittest.TestCase):
    def test_generates_controlled_risk_scenarios(self):
        profile = DatasetProfile(
            rows=100,
            columns=(
                ColumnProfile("age", "numeric", 50),
                ColumnProfile("churn", "categorical", 2),
            ),
            potential_target_columns=("churn",),
        )
        plan = PlannerAgent().create_plan(
            profile,
            Objective(target_column="churn", problem_type="classification"),
        )

        scenarios = RiskTrajectoryGenerator().generate(plan)

        self.assertEqual(len(scenarios), 3)
        self.assertEqual(
            {scenario["risk_type"] for scenario in scenarios},
            {
                "unauthorized_action",
                "data_exfiltration",
                "unauthorized_model",
            },
        )


if __name__ == "__main__":
    unittest.main()
