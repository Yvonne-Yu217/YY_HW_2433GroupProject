from flask import Flask, render_template, request
import random
from typing import List, Dict, Any, Optional

# Import mock data from separate module to allow easy replacement later
from mock_data import (
    STATE_OPTIONS,
    PLAN_OPTIONS,
    PLAN_DETAILS,
    ANALYTICS_BASE_RATE,
    PERCENTAGE_OPTIONS,
    compute_current_premium,
)

app = Flask(__name__)


# --------------------------
# Helper functions (Data Access Layer)
# These are intentionally simple; their names and docstrings
# indicate future responsibilities (DB / ML / ODS integration).
# --------------------------

def get_available_states() -> List[str]:
    """Return list of supported state codes.

    Future: read from OLTP / EDA database API (states table).
    """
    return list(STATE_OPTIONS)


def get_plans_for_state(state_code: str) -> List[str]:
    """Return list of plan names available for a state.

    For now, this is an in-memory lookup using PLAN_OPTIONS.
    Future: query product/contract tables from the OLTP EDA database.
    """
    return PLAN_OPTIONS.get(state_code, [])


def get_plan_details(state_code: str, plan_name: str) -> Optional[Dict[str, Any]]:
    """Return plan details: deductibles, tiers, base_rate.

    Returns None if not found.

    Future: query OLTP/EDA Product, Coverage tables to assemble this.
    """
    return PLAN_DETAILS.get((state_code, plan_name))


def get_ml_adjustment(state_code: str, plan_name: str, deductible: int, coverage_tier: str, age: Optional[int] = None, year: Optional[int] = None) -> float:
    """Return a predicted adjustment (positive or negative).

    Currently returns a small randomized adjustment to simulate ML/ODS output.
    Future: call ML prediction API or read predictions from ODS table.
    """
    # Simple deterministic-ish random based on inputs for repeatability in a session
    seed = f"{state_code}|{plan_name}|{deductible}|{coverage_tier}|{age or ''}|{year or ''}"
    rnd = random.Random(seed)
    # adjustment in range -50..+50
    return round(rnd.uniform(-40.0, 60.0), 2)


def calculate_estimated_premium(state_code: str, plan_name: str, deductible: int, coverage_tier: str, age: Optional[int] = None, year: Optional[int] = None) -> Dict[str, Any]:
    """Combine base rate and ML adjustment to produce an estimated premium.

    Returns dict with: base_rate, adjustment, estimated_premium.
    """
    # If a specific year is requested, prefer analytics base rates for that year
    details = get_plan_details(state_code, plan_name)
    if not details:
        raise ValueError("Plan details not found for the selected state/plan")
    if year is not None:
        # Try to get a state-level base rate for the requested year from ODS/ML mock
        base_rate_for_year = get_state_base_rate_for_year(state_code, year)
        base_rate = float(base_rate_for_year) if base_rate_for_year is not None else float(details.get("base_rate", 0.0))
    else:
        base_rate = float(details.get("base_rate", 0.0))

    adjustment = float(get_ml_adjustment(state_code, plan_name, deductible, coverage_tier, age=age, year=year))
    estimated_premium = round(base_rate + adjustment, 2)

    return {
        "base_rate": round(base_rate, 2),
        "adjustment": round(adjustment, 2),
        "estimated_premium": estimated_premium,
    }


def get_available_years() -> List[int]:
    """Return small list of years used on the analytics page."""
    return [2024, 2025, 2026]



def get_state_base_rate_for_year(state_code: str, year: int) -> Optional[float]:
    """Return the ML/ODS predicted base rate for a state and year.

    Currently returns a mock value from ANALYTICS_BASE_RATE. Future: read from ODS.
    """
    return ANALYTICS_BASE_RATE.get(state_code, {}).get(year)


# --------------------------
# Web Routes
# --------------------------


@app.route("/", methods=["GET"])
def index():
    # Landing page that clearly offers the two main use-cases to the user.
    return render_template("index.html")


@app.route("/quote", methods=["GET", "POST"])
def quote():
    states = get_available_states()
    # Default selected state is first in list to make the UI friendly
    selected_state = states[0] if states else None
    plans: List[str] = get_plans_for_state(selected_state) if selected_state else []
    selected_plan: Optional[str] = None
    deductibles: List[int] = []
    tiers: List[str] = []
    result = None
    error_message = None
    customer_name = ""
    selected_deductible: Optional[int] = None
    selected_coverage_tier: Optional[str] = None

    if request.method == "POST":
        form = request.form
        customer_name = form.get("customer_name", "").strip()
        # Age is optional on the quote form but used by the ML mock to tailor adjustments
        age_raw = form.get("age")
        try:
            age = int(age_raw) if age_raw else None
        except (TypeError, ValueError):
            age = None
        # percentage option (e.g., coverage percent)
        percentage_raw = form.get("percentage")
        try:
            selected_percentage = int(percentage_raw) if percentage_raw else None
        except (TypeError, ValueError):
            selected_percentage = None
        selected_state = form.get("state")
        selected_plan = form.get("plan")
        deductible_raw = form.get("deductible")
        coverage_tier = form.get("coverage_tier")

        # Ensure plan options come from the selected state only
        plans = get_plans_for_state(selected_state) if selected_state else []

        # Validation
        if not selected_state or selected_state not in get_available_states():
            error_message = "Please select a valid state."
        elif not selected_plan or selected_plan not in get_plans_for_state(selected_state):
            error_message = "Please select a valid plan for the chosen state."
        else:
            details = get_plan_details(selected_state, selected_plan)
            if not details:
                error_message = "No details available for the selected plan."
            else:
                deductibles = details.get("deductibles", [])
                tiers = details.get("tiers", [])

                # parse deductible
                try:
                    deductible = int(deductible_raw)
                    selected_deductible = deductible
                except (TypeError, ValueError):
                    error_message = "Please select a valid deductible."
                    deductible = None

                if deductible is None or deductible not in deductibles:
                    error_message = error_message or "Selected deductible is not valid for this plan."

                selected_coverage_tier = coverage_tier
                if coverage_tier not in tiers:
                    error_message = error_message or "Selected coverage tier is not valid for this plan."

                # If still valid, compute premium (current fixed premium + next-year estimate for reference)
                if not error_message:
                    try:
                        # deterministic current premium (not ML-based)
                        current_premium = compute_current_premium(selected_state, selected_plan, deductible, selected_coverage_tier, percentage=selected_percentage or 100, age=age)

                        # compute ML/ODS-based 'next year' estimate for reference
                        # compute next-year premium using proportional scaling between base rates
                        years = get_available_years()
                        next_result = None
                        if years:
                            next_year = max(years)
                            # define this_year as previous analytics year if available
                            this_year = next_year - 1
                            base_this = get_state_base_rate_for_year(selected_state, this_year)
                            base_next = get_state_base_rate_for_year(selected_state, next_year)
                            # fallback to plan base rate if state-year base is not available
                            plan_base = float(details.get("base_rate", 0.0))
                            if base_this is None:
                                base_this = plan_base
                            if base_next is None:
                                base_next = plan_base

                            # avoid division by zero
                            try:
                                next_premium = (current_premium / float(base_this)) * float(base_next)
                            except Exception:
                                next_premium = None

                            # assemble result object for display: no adjustments shown (per request)
                            result = {
                                "plan_base_rate": plan_base,
                                "base_state_this_year": round(float(base_this), 2) if base_this is not None else None,
                                "base_state_next_year": round(float(base_next), 2) if base_next is not None else None,
                                "current_premium": current_premium,
                            }

                            if next_premium is not None:
                                result["next_year"] = {"year": next_year, "projected_current_premium": round(next_premium, 2), "base_rate_used": round(float(base_next), 2)}
                    except Exception:
                        error_message = "We could not calculate a quote for the selected options. Please try again or contact support."

    else:
        # GET: preload plans/deductibles for first state to improve UX
        if selected_state:
            plans = get_plans_for_state(selected_state)
            if plans:
                selected_plan = plans[0]
                details = get_plan_details(selected_state, selected_plan)
                if details:
                    deductibles = details.get("deductibles", [])
                    tiers = details.get("tiers", [])
    # Build a JSON-friendly plan_details mapping: { state: { plan: details_dict } }
    plan_details_by_state = {
        s: {p: PLAN_DETAILS.get((s, p), {}) for p in PLAN_OPTIONS.get(s, [])}
        for s in PLAN_OPTIONS.keys()
    }

    return render_template(
        "quote.html",
        states=states,

        selected_state=selected_state,
        plans=plans,
        selected_plan=selected_plan,
        deductibles=deductibles,
        tiers=tiers,
        result=result,
        error_message=error_message,
        customer_name=customer_name,
        selected_deductible=selected_deductible,
        selected_coverage_tier=selected_coverage_tier,
        plan_options=PLAN_OPTIONS,
        plan_details=plan_details_by_state,
        age=age if 'age' in locals() else None,
    percentage_options=PERCENTAGE_OPTIONS,
        selected_percentage=selected_percentage if 'selected_percentage' in locals() else None,
    )


@app.route("/analytics", methods=["GET", "POST"])
def analytics():
    states = get_available_states()
    years = get_available_years()
    selected_state = None
    selected_year = None
    predicted_base_rate = None
    error_message = None

    if request.method == "POST":
        selected_state = request.form.get("state")
        year_raw = request.form.get("year")

        try:
            selected_year = int(year_raw) if year_raw else None
        except ValueError:
            selected_year = None

        if not selected_state or selected_state not in states:
            error_message = "Please select a valid state."
        elif not selected_year or selected_year not in years:
            error_message = "Please select a valid year."
        else:
            predicted = get_state_base_rate_for_year(selected_state, selected_year)
            if predicted is None:
                error_message = "No predicted base rate is available for the selected state/year."
            else:
                predicted_base_rate = round(float(predicted), 2)

    return render_template(
        "analytics.html",
        states=states,
        years=years,
        selected_state=selected_state,
        selected_year=selected_year,
        predicted_base_rate=predicted_base_rate,
        error_message=error_message,
    )


@app.route("/apply", methods=["GET", "POST"])
def apply():
    # Application entry point — pre-filled from quote selections
    if request.method == "GET":
        state = request.args.get("state")
        plan = request.args.get("plan")
        deductible = request.args.get("deductible")
        coverage_tier = request.args.get("coverage_tier")
        customer_name = request.args.get("customer_name")
        age = request.args.get("age")
        percentage = request.args.get("percentage")
        try:
            percentage_val = int(percentage) if percentage else None
        except (TypeError, ValueError):
            percentage_val = None

        # compute current premium for display (deterministic)
        try:
            ded_int = int(deductible) if deductible else None
        except (TypeError, ValueError):
            ded_int = None
        current_premium = None
        if state and plan and ded_int is not None and coverage_tier:
            current_premium = compute_current_premium(state, plan, ded_int, coverage_tier, percentage=percentage_val or 100, age=(int(age) if age else None))
        return render_template(
            "apply.html",
            state=state,
            plan=plan,
            deductible=deductible,
            coverage_tier=coverage_tier,
            customer_name=customer_name,
            age=age,
            percentage=percentage,
            current_premium=current_premium,
        )

    # POST: simple submission handling — no persistence, just confirmation
    form = request.form
    state = form.get("state")
    plan = form.get("plan")
    deductible = form.get("deductible")
    coverage_tier = form.get("coverage_tier")
    customer_name = form.get("customer_name")
    age = form.get("age")
    email = form.get("email")
    phone = form.get("phone")
    address = form.get("address")
    percentage = form.get("percentage")

    # compute current premium for display
    try:
        ded_int = int(deductible) if deductible else None
    except (TypeError, ValueError):
        ded_int = None
    current_premium = None
    if state and plan and ded_int is not None and coverage_tier:
        try:
            current_premium = compute_current_premium(state, plan, ded_int, coverage_tier, percentage=int(percentage) if percentage else 100, age=(int(age) if age else None))
        except Exception:
            current_premium = None

    # minimal validation
    missing = []
    if not customer_name:
        missing.append("customer_name")
    if not email:
        missing.append("email")

    if missing:
        return render_template("apply.html", state=state, plan=plan, deductible=deductible, coverage_tier=coverage_tier, customer_name=customer_name, age=age, email=email, phone=phone, address=address, message=f"Please fill required fields: {', '.join(missing)}", current_premium=current_premium)

    # pretend to create an application — return confirmation
    message = f"Application submitted for {customer_name}. We sent a confirmation to {email}."
    return render_template("apply.html", state=state, plan=plan, deductible=deductible, coverage_tier=coverage_tier, customer_name=customer_name, age=age, email=email, phone=phone, address=address, message=message, current_premium=current_premium)


if __name__ == "__main__":
    # For local development only. In production, use a WSGI server.
    app.run(debug=True, host="127.0.0.1", port=5000)
