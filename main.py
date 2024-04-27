from flask import Flask, request, jsonify
import google.generativeai as genai
import requests
import re

app = Flask(__name__)

# Configure the Google Generative AI with your API key
genai.configure(api_key="AIzaSyBGKoa3KZlNDac_qW0XuRyXGfa1aJqpQmQ")

# Initialize the GenerativeModel
model = genai.GenerativeModel('gemini-pro')
NODE_SERVER_URL = 'http://localhost:3000/modules/receive_modules'


def generate_steps(task_description):
    # Generate input text for the GenerativeModel
    input_text = f"generate for me a small text to help and advice for this {task_description} make it a short and simple text with no special caracters "

    # Generate content using the GenerativeModel
    generated_content = model.generate_content(input_text)

    # Extract steps from the generated content
    generated_content_text = generated_content.text

    return generated_content_text

@app.route('/generate-steps', methods=['POST'])
def generate_steps_endpoint():
    # Get title from the request
    data = request.get_json()
    task_description = data.get('task_description')

    # Generate steps based on title
    steps = generate_steps(task_description)

    # Prepare response
    response = {
        "text": steps
    }

    return jsonify(response)

# Add a new route to receive task titles from the Node.js application
@app.route('/task-title', methods=['POST'])
def receive_task_title():
    data = request.get_json()
    task_description = data.get('task_description')

    # Generate steps based on the received title
    steps = generate_steps(task_description)

    # Prepare response
    response = {
        "text": steps
    }

    return jsonify(response)


@app.route('/generate_project_modules', methods=['POST'])
def generate_project_modules():
    data = request.get_json()
    project_id = data.get('_id', None)

    if project_id is None:
        return jsonify({"error": "Project ID not found in request data"})

    # Fetch members (users) of the project from the request data
    members = data.get('members', [])

    # Initialize input text with project details
    input_text = f"Generate the modules and the steps for each module for {data.get('name')}.\n\n"
    input_text += f"Project Description: {data.get('description')}\n"
    input_text += f"Some keywords: {data.get('keywords')}\n"

    # Initialize dictionary to store team members for each module
    module_teams = {}

    for member in members:
        try:
            # Assuming you have an endpoint to fetch user specialties in your Node.js server
            response = requests.get(f"http://localhost:3000/user-specialties/{member}")
            specialty = response.json().get('specialty', "")
            # Debug statement to check member and specialty
            print(f"Member: {member}, Specialty: {specialty}")
            input_text += f"- {member}: {specialty}\n"
        except Exception as e:
            print("Error fetching specialties for member:", str(e))

    input_text += f"Module and step format: **Module 1 : Data Collection** * **Step 1:** Description.(userEmail)\n"

    # Generate content using the GenerativeModel
    generated_content = model.generate_content(input_text)
    generated_content_text = generated_content.text

    modules = []
    tasks = []
    current_module = None

    for line in generated_content_text.split('\n'):
        if line.startswith("**"):
            if current_module:
                # Add the current module and its tasks to the modules list
                unique_team_members = list(set(module_teams.get(current_module, [])))  # Convert set back to list
                modules.append({"module_name": current_module, "tasks": tasks, "teamM": unique_team_members})
                tasks = []
            current_module = line.split(":")[1].strip().rstrip('**')
        elif line.startswith("*"):
            task_description = line.split(":")[1].strip().lstrip('**')
            # Extracting emails between parentheses
            emails = re.findall(r'\(([^)]+)\)', task_description)
            # Removing emails from the task description
            task_name = re.sub(r'\([^)]*\)', '', task_description).strip()
            # Extracted emails from the task description
            team = [email.strip() for email in emails[0].split(',')] if emails else []
            # Add team members to the module_teams dictionary
            module_teams.setdefault(current_module, []).extend(team)
            # Creating the task object
            tasks.append({"task_name": task_name, "projectID": project_id, "team": team})
    if current_module:
        modules.append({"module_name": current_module, "tasks": tasks, "teamM": module_teams.get(current_module, [])})

    print("Generated Modules:", modules)

    try:
        # Posting to the Node.js server
        response = requests.post(NODE_SERVER_URL, json={"projectID": project_id, "modules": modules})
        response_data = response.json()
        print("Response from Node Server:", response_data)

        # Debug statements for checking data being sent to the Node.js server
        for module in modules:
            print("Data sent to Node.js server:")
            print("Module Name:", module['module_name'])
            print("TeamM:", module['teamM'])

        return jsonify({"message": "Modules sent successfully", "response": response_data})
    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": f"Failed to send modules: {str(e)}"})



if __name__ == '__main__':
    app.run(debug=True, port=5000)
