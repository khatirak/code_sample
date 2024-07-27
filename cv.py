import os
import time
from flask import Flask, request, jsonify
from groq import Groq
from datetime import datetime, timedelta
import base64
from io import BytesIO
from docx import Document

# Setting up environment variable
os.environ['GROQ_API_KEY'] = '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'

app = Flask(__name__)
last_request_time = datetime.now()
request_interval = timedelta(seconds=2)  # to respect the retry-after rate limit

questions = [
    "What is your current job title?",
    "What industry are you in?", 
    "What role are you seeking?",
    "What are your top 3 skills?",
    "What are your career goals?",
    "What makes you stand out from other candidates?",
    "What are your biggest career achievements?",
    "Please upload your current CV."
]

sections = {
    "Summary": [
        "Brief overview of your professional background and goals"
    ],
    "Work Experience": [
        "List your work history, starting with the most recent",
        "Include company name, job title, dates, and key responsibilities/achievements"
    ],
    "Skills": [
        "Highlight your top skills relevant to the desired role"  
    ],
    "Education": [
        "List your educational background, including degree, institution, and graduation year"
    ],
    "Achievements": [
        "Mention any notable accomplishments, awards, or projects"
    ]
}

def refine_user_input(user_responses):
    global last_request_time
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    if (datetime.now() - last_request_time) < request_interval:
        time.sleep((request_interval - (datetime.now() - last_request_time)).total_seconds()) 

    prompt = f"""
    Based on the following user responses, provide concise and focused answers suitable for a CV:

    User Responses:
    {user_responses}

    Please answer these questions:  
    """
    for question in questions[:-1]:  # Exclude the last question
        prompt += f"\n- {question}"

    completion_params = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}], 
        "temperature": 0.7,
        "max_tokens": 500,
        "top_p": 1,
        "stream": True, 
        "stop": None,
    }

    try:
        completion = client.chat.completions.create(**completion_params)
        refined_content = [] 
        for chunk in completion:
            refined_content.append(chunk.choices[0].delta.content or "")
        refined_text = ''.join(refined_content)

        # Parse into individual answers
        refined_responses = {} 
        for i, question in enumerate(questions[:-1]):  # Exclude the last question
            start = refined_text.find(question) + len(question)
            end = refined_text.find(questions[i+1], start) if i < len(questions) - 1 else None
            answer = refined_text[start:end].strip()
            refined_responses[question] = answer

        # Handle the CV upload question separately
        refined_responses[questions[-1]] = "CV successfully uploaded"  # Or simply "True"

        last_request_time = datetime.now()
        return refined_responses
    except Exception as e:
        return f"An error occurred while refining input: {e}"

@app.route('/api/jobseeker', methods=['POST'])  
def main():
    user_responses = request.get_json()

    content = user_responses["user_responses"]["Please upload your current CV."]["content"]
    if content:
        # decoded_data = base64.b64decode(base64_data)
        decoded_content = base64.b64decode(content)
        
        doc = Document(BytesIO(decoded_content))
        # Extract text from the .docx file
        full_text = []  
        for paragraph in doc.paragraphs:
            full_text.append(paragraph.text)
        
        # Join the full text into a single string
        full_text_str = '\n'.join(full_text)
        
        # Replace the content in the user_responses with the extracted text
        user_responses["user_responses"]["Please upload your current CV."]["content"] = full_text_str
 
    # Refine user input
    refined_responses = refine_user_input(user_responses)
    
    # Generate CV using refined responses
    cv = {}
    context = "\n".join([f"{q}: {a}" for q, a in refined_responses.items()])

    for section, prompts in sections.items():
        section_content = generate_section(section, prompts, context)  
        cv[section] = section_content

    return jsonify({'message': 'CV generated', 'cv': cv, 'refined_responses': refined_responses})

def generate_section(section, prompts, context):
    global last_request_time
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    if (datetime.now() - last_request_time) < request_interval:
        time.sleep((request_interval - (datetime.now() - last_request_time)).total_seconds())

    prompt = f"""Generate concise content for the {section} section of a CV: 

    Context:
    {context}

    Include the following points:
    """ 
    for prompt_item in prompts:
        prompt += f"- {prompt_item}\n"

    completion_params = { 
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7, 
        "max_tokens": 200,
        "top_p": 1,
        "stream": True,
        "stop": None, 
    }

    try:
        completion = client.chat.completions.create(**completion_params)
        section_content = []
        for chunk in completion:  
            section_content.append(chunk.choices[0].delta.content or "")
        last_request_time = datetime.now()
        return ''.join(section_content)
    except Exception as e:
        return f"An error occurred: {e}"   

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)