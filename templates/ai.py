import google.generativeai as genai

# Configure API Key
genai.configure(api_key="YOUR_API_KEY")

# Gemini Model
model = genai.GenerativeModel("gemini-1.5-flash")


# ================= VEHICLE RECOMMENDATION =================

def recommend_vehicle(budget, passengers, trip_type):

    prompt = f"""
    Suggest the best rental vehicle.

    Budget: {budget}
    Passengers: {passengers}
    Trip Type: {trip_type}

    Give:
    1. Vehicle Name
    2. Short Reason
    """

    response = model.generate_content(prompt)

    return response.text


# ================= CHATBOT =================

def chatbot_response(user_message):

    prompt = f"""
    You are an AI assistant for a vehicle rental platform called Rent A Ride.

    User Question:
    {user_message}

    Answer shortly and professionally.
    """

    response = model.generate_content(prompt)

    return response.text