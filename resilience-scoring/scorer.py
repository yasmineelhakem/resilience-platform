
def compute_resilience_score(
    availability_pct: float,
    mttr_seconds: float,
    burn_rate: float,
    mttr_ceiling_sec: float = 180,   # Target max recovery time     todooooo 300
    max_burn_rate: float = 10.0,      # Worst-case burn rate ceiling
    weights: tuple = (0.35, 0.35, 0.30)
) -> dict:
    w_avail, w_mttr, w_burn = weights

    # 1. Availability Score (0-100)
    score_avail = max(0.0, min(100.0, availability_pct))

    # 2. MTTR Score (0-100)

    if mttr_seconds is None:
        score_mttr = 0.0 # todooooo: f 100 (network partitioning fiha 0 )
    else:
        score_mttr = max(0.0, 100.0 * (1.0 - (mttr_seconds / mttr_ceiling_sec)))

    # 3. Burn Rate Score (0-100)
    capped_burn = min(burn_rate, max_burn_rate)
    score_burn = max(0.0, 100.0 * (1.0 - (capped_burn / max_burn_rate)))

    # 4. Final Weighted Resilience Score
    total_score = (score_avail * w_avail) + (score_mttr * w_mttr) + (score_burn * w_burn)

    return {
        "availability_score": round(score_avail, 1),
        "mttr_score": round(score_mttr, 1),
        "burn_rate_score": round(score_burn, 1),
        "final_resilience_score": round(total_score, 1)
    }


def calculate_burn_rate(availability_pct: float, slo_target: float = 0.99) -> float:
    """
    Calculates error budget burn rate based on actual availability vs target SLO.
    """
    actual_unreliability = max(0.0001, (100.0 - availability_pct) / 100.0)
    allowed_unreliability = 1.0 - slo_target  # e.g., 0.01 for 99% SLO
    return round(actual_unreliability / allowed_unreliability, 2)
