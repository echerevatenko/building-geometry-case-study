from enum import StrEnum


class VerificationStatus(StrEnum):
    FEASIBLE = "feasible"  # verification passed
    INFEASIBLE = "infeasible"  # verification failed
