def final_decision(score):

    if score >= 80:
        return "Strong Hire"
    elif score >= 50:
        return "Consider"
    else:
        return "Reject"