import math
from typing import List, Dict, Tuple, Any
from app.errors import AppException
from fastapi import status


def calculate_participant_shares(
    total_amount: int,
    split_type: str,
    participants_info: List[Dict[str, Any]],  # [{'user_id': int, 'username': str, 'input': ParticipantInput}]
    remainder_bearer_id: int | None,
) -> Tuple[List[Dict[str, Any]], int | None]:
    """
    Compute whole-rupee share amounts for each participant (FR-061, FR-062).
    Enforces exact sum invariant: sum(shares) == total_amount.
    If remainder > 0, remainder is allocated to the chosen remainder_bearer_id.
    """
    participant_user_ids = [p["user_id"] for p in participants_info]
    num_parts = len(participants_info)

    if num_parts == 0:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="NO_PARTICIPANTS",
            message="A split must have at least one participant.",
        )

    shares: Dict[int, int] = {}

    if split_type == "exact":
        total_given = 0
        for p in participants_info:
            amt = p["input"].amount
            if amt is None or amt < 0:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_EXACT_AMOUNT",
                    message=f"Missing or invalid exact amount for user {p['username']}.",
                )
            shares[p["user_id"]] = amt
            total_given += amt

        if total_given != total_amount:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="EXACT_SPLIT_SUM_MISMATCH",
                message=f"Sum of exact shares (₹{total_given}) does not match bill amount (₹{total_amount}).",
            )
        resolved_remainder_bearer = None

    elif split_type == "percentage":
        total_pct = sum(p["input"].percentage or 0.0 for p in participants_info)
        if abs(total_pct - 100.0) > 0.001:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="PERCENTAGE_SUM_MISMATCH",
                message=f"Sum of percentages ({total_pct:.1f}%) must equal exactly 100%.",
            )

        base_sum = 0
        for p in participants_info:
            pct = p["input"].percentage or 0.0
            base_amt = int(math.floor(total_amount * (pct / 100.0)))
            shares[p["user_id"]] = base_amt
            base_sum += base_amt

        remainder = total_amount - base_sum
        resolved_remainder_bearer = remainder_bearer_id

        if remainder > 0:
            if not remainder_bearer_id or remainder_bearer_id not in participant_user_ids:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="REMAINDER_BEARER_REQUIRED",
                    message=f"A remainder of ₹{remainder} exists. Please select which participant bears the remainder.",
                )
            shares[remainder_bearer_id] += remainder

    elif split_type == "shares":
        total_weights = sum(p["input"].shares or 1 for p in participants_info)
        base_sum = 0
        for p in participants_info:
            weight = p["input"].shares or 1
            base_amt = int(math.floor(total_amount * (weight / total_weights)))
            shares[p["user_id"]] = base_amt
            base_sum += base_amt

        remainder = total_amount - base_sum
        resolved_remainder_bearer = remainder_bearer_id

        if remainder > 0:
            if not remainder_bearer_id or remainder_bearer_id not in participant_user_ids:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="REMAINDER_BEARER_REQUIRED",
                    message=f"A remainder of ₹{remainder} exists. Please select which participant bears the remainder.",
                )
            shares[remainder_bearer_id] += remainder

    else:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_SPLIT_TYPE",
            message=f"Unknown split type '{split_type}'.",
        )

    # Invariant assertion
    if sum(shares.values()) != total_amount:
        raise AppException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="MATH_INVARIANT_VIOLATION",
            message="Internal calculation error: shares sum does not equal total bill amount.",
        )

    result = []
    for p in participants_info:
        result.append({
            "user_id": p["user_id"],
            "username": p["username"],
            "share_amount": shares[p["user_id"]],
        })

    return result, resolved_remainder_bearer
