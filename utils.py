# utils.py
from datetime import datetime, timedelta

# Commission tier dictionary
COMMISSION_TIERS = {
    "LOA5": 0.05,
    "LOA20": 0.20,
    "Independent": None  # Customize logic for independent agents if necessary
}

def calculate_commission_due(commissionable_premium, commission_tier):
    """Calculate commission due based on tier."""
    percentage_due = COMMISSION_TIERS.get(commission_tier, 0)
    return commissionable_premium * percentage_due

def should_switch_to_loa20(hire_date):
    """Check if agent should be auto-switched to LOA20 after 6 months."""
    six_months_later = hire_date + timedelta(days=180)
    return datetime.now().date() >= six_months_later
from datetime import datetime, timedelta
import sqlite3
from utils import should_switch_to_loa20

def switch_commission_tier(agent_id, secret_code=None):
    """Switch the commission tier for an agent."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    # Fetch agent details
    cursor.execute("SELECT hire_date, commission_tier, secret_code FROM agents WHERE id = ?", (agent_id,))
    agent = cursor.fetchone()
    if not agent:
        conn.close()
        return {"error": "Agent not found."}

    hire_date, current_tier, agent_secret_code = agent

    # Automatic switch logic
    if should_switch_to_loa20(hire_date) and current_tier == "LOA5":
        new_tier = "LOA20"
    # Manual switch with secret code
    elif secret_code and secret_code == agent_secret_code:
        new_tier = "LOA20" if current_tier == "LOA5" else "Independent"
    else:
        conn.close()
        return {"error": "Switch not allowed."}

    # Update the tier
    cursor.execute("UPDATE agents SET commission_tier = ? WHERE id = ?", (new_tier, agent_id))
    conn.commit()
    conn.close()

    return {"success": True, "new_tier": new_tier}
