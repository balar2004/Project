from flask import Flask,render_template,Response,request, send_from_directory,session, send_file, jsonify, request,flash,redirect,url_for
import sqlite3
import smtplib
from email.mime.text import MIMEText
from pytesseract import pytesseract
import cv2
import pyttsx3
import re
import nltk
nltk.download('punkt_tab')
nltk.download('wordnet')
from keras.models import load_model
from nltk.stem import WordNetLemmatizer
import speech_recognition as sr
from gtts import gTTS
import os
from googletrans import Translator
import random
import numpy as np
import pickle
import json
import speech_recognition as sr

lemmatizer = WordNetLemmatizer()

app = Flask(__name__)
app.config['SECRET_KEY'] = '7103'

model = load_model("chatbot_model.h5")
intents = json.loads(open("intents.json").read())
words = pickle.load(open("words.pkl", "rb"))
classes = pickle.load(open("classes.pkl", "rb"))

database="Expenses.db"

def createtable():
    conn=sqlite3.connect(database)
    cursor=conn.cursor()
    cursor.execute("create table if not exists register(id integer primary key autoincrement, name text,email text,password text,status text)")
    cursor.execute('''CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT,
                    month TEXT,
                    income REAL,
                    emi REAL,
                    groceries REAL,
                    utilities REAL,
                    rent REAL,
                    transport REAL,
                    shopping REAL,
                    entertainment REAL,
                    savings REAL,
                    total_expense REAL
                )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS expenses_bill (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT,
                    month TEXT,
                    income REAL,
                    emi REAL,
                    groceries REAL,
                    utilities REAL,
                    rent REAL,
                    transport REAL,
                    shopping REAL,
                    entertainment REAL,
                    savings REAL,
                    receipt TEXT,
                    total_expense REAL
                )''')
    conn.commit()
    conn.close()
createtable()

@app.route('/')
def home():
    return render_template('register.html')

@app.route('/expenses_details')
def expenses_details():
    return render_template('expenses_details.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/ocr')
def ocr():
    return render_template('ocr.html')

@app.route('/register', methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form['name']
        email=request.form['email']
        password=request.form['password']
        conn=sqlite3.connect(database)
        cursor=conn.cursor()
        cursor.execute(" SELECT email FROM register WHERE email=?",(email,))
        registered=cursor.fetchall()
        if registered:
            return render_template('register.html', alert_message="Email Already Registered")
        else:
            cursor.execute("insert into register(name,email,password,status) values(?,?,?,?)",(name,email,password,0))
            conn.commit()
            return render_template('login.html', alert_message="Registered Succussfully")
    return render_template('register.html')

@app.route('/login', methods=["GET", "POST"])
def login():
    global data
    global email
    if request.method == "POST":        
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM register WHERE email=? AND password=?", (email, password))
        data = cursor.fetchone()

        if data is None:
            return render_template('register.html', alert_message="Email Not Registered or Check Password")
        else:
            session['email'] = email
            return render_template('dashboard.html')

    return render_template('login.html')

def send_alert_email1(to_email, month, income, expense_data, total_expense, limit):
    expense_details = "\n".join([f"{field.capitalize()}: ₹{expense}" for field, expense in expense_data.items()])
    
    msg = MIMEText(f"""
    Alert: Your total monthly expenses ₹{total_expense} have exceeded the limit of ₹{limit}.

    Expense Details for the month of {month}:
    Income: ₹{income}
    {expense_details}
    
    Total Expenses: ₹{total_expense}
    """)
    msg['Subject'] = 'Monthly Expense Alert 🚨'
    msg['From'] = 'Expense_Alert@gmail.com'  
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login('admin@gmail.com', 'admin123')  
            server.send_message(msg)
        print("Email sent successfully.")
    except Exception as e:
        print("Email send failed:", e)

@app.route('/expenses', methods=['GET', 'POST'])
def expenses():
    if request.method == 'POST':
        email = session['email']
        month = request.form['month']
        income = float(request.form['income'])

        fields = ['emi', 'groceries', 'utilities', 'rent', 'transport', 'shopping', 'entertainment', 'savings']
        expense_data = {field: float(request.form.get(field, 0)) for field in fields}
        total_expense = sum(expense_data.values())
        threshold_margin = 5000
        expense_limit = income - threshold_margin

        conn = sqlite3.connect(database)
        c = conn.cursor()

        c.execute("SELECT * FROM expenses WHERE email=? AND month=?", (email, month))
        existing = c.fetchone()

        if existing:
            c.execute('''UPDATE expenses SET income=?, emi=?, groceries=?, utilities=?, rent=?, 
                         transport=?, shopping=?, entertainment=?, savings=?, total_expense=?
                         WHERE email=? AND month=?''',
                      (income, *expense_data.values(), total_expense, email, month))
        else:
            c.execute('''INSERT INTO expenses (email, month, income, emi, groceries, utilities, rent,
                         transport, shopping, entertainment, savings, total_expense)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (email, month, income, *expense_data.values(), total_expense))

        conn.commit()
        conn.close()
        if total_expense > expense_limit:
            send_alert_email1(email, month, income, expense_data, total_expense, expense_limit)

        return render_template('dashboard.html', alert_message='Expense data submitted/updated successfully!')

    return render_template('dashboard.html')

import os
from PIL import Image

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- TESSERACT PATH CONFIGURATION ---
path_to_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe" 

if os.path.exists(path_to_tesseract):
    pytesseract.tesseract_cmd = path_to_tesseract
else:
    # Fallback to x86 path if the above doesn't exist
    path_to_tesseract = r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
    pytesseract.tesseract_cmd = path_to_tesseract
# ------------------------------------

def preprocess_image(image_path):
    image = cv2.imread(image_path)
    image = cv2.resize(image, (1000, 900))  
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast_img = clahe.apply(gray)

    _, thresh = cv2.threshold(contrast_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return thresh

def extract_total_amount(text):
    matches = re.findall(r'TOTAL[-:\s]*₹?(\d+)', text, re.IGNORECASE)
    if matches:
        return float(matches[-1])
    return 0.0

def extract_product_type(text):
    match = re.search(r'Product[:\s]+([A-Za-z]+)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip().lower()  # e.g., 'shopping'
    return ""

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['image']
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        preprocessed_img = preprocess_image(filepath)
        custom_config = r'--oem 3 --psm 4'
        extracted_text = pytesseract.image_to_string(preprocessed_img, config=custom_config)
        print(extracted_text)
        ocr_total = extract_total_amount(extracted_text)
        print(ocr_total)

        product_type = extract_product_type(extracted_text)
        print(product_type)
        
        email = session.get('email')
        conn = sqlite3.connect(database)
        c = conn.cursor()
        c.execute("SELECT month,income, emi, groceries, utilities, rent, transport, shopping, entertainment, savings FROM expenses WHERE email = ? ORDER BY id DESC LIMIT 1", (email,))
        row = c.fetchone()

        if row:
            month = row[0]
            income, emi, groceries, utilities, rent, transport, shopping, entertainment, savings = map(float, row[1:])

            # Add extracted amount to correct category
            if product_type == 'shopping':
                shopping += ocr_total
            elif product_type == 'groceries':
                groceries += ocr_total
            elif product_type == 'transport':
                transport += ocr_total
            elif product_type == 'utilities':
                utilities += ocr_total
            elif product_type == 'rent':
                rent += ocr_total
            elif product_type == 'entertainment':
                entertainment += ocr_total
            elif product_type == 'emi':
                emi += ocr_total
            elif product_type == 'savings':
                savings += ocr_total

            combined_total = emi + groceries + utilities + rent + transport + shopping + entertainment + savings

            threshold_margin = 5000
            if combined_total > (income - threshold_margin):
                send_alert_email(
                    email=email,
                    subject="Expense Alert",
                    body=f"""📅 Monthly Expenses Summary
Income: ₹{income}
EMI: ₹{emi}
Groceries: ₹{groceries}
Utilities: ₹{utilities}
Rent: ₹{rent}
Transport: ₹{transport}
Shopping: ₹{shopping}
Entertainment: ₹{entertainment}
Savings: ₹{savings}

🧾 New Expense from Receipt: ₹{ocr_total} ({product_type.capitalize()})
💸 Total Expenses This Month: ₹{combined_total}

⚠️ Alert: Your total expenses exceeded your income by ₹{combined_total - income}"""
                )
                alert = f"⚠️ Alert sent! Your total expenses ₹{combined_total} exceed your income ₹{income}."
            else:
                alert = f"✅ No alert needed. Your total expenses ₹{combined_total} are within the income ₹{income}."

            c.execute('''INSERT INTO expenses_bill (
                            email, month, income, emi, groceries, utilities,
                            rent, transport, shopping, entertainment, savings,receipt,
                            total_expense
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)''',
                      (email, month, income, emi, groceries, utilities,
                       rent, transport, shopping, entertainment, savings,str(ocr_total),
                       combined_total))
            conn.commit()
            import matplotlib.pyplot as plt

            # Create pie chart
            labels = ['EMI', 'Groceries', 'Utilities', 'Rent', 'Transport', 'Shopping', 'Entertainment', 'Savings']
            values = [emi, groceries, utilities, rent, transport, shopping, entertainment, savings]
            filtered_labels = [label for i, label in enumerate(labels) if values[i] > 0]
            filtered_values = [value for value in values if value > 0]

            plt.figure(figsize=(6, 6))
            plt.pie(filtered_values, labels=filtered_labels, autopct='%1.1f%%', startangle=140)
            plt.title(f"Monthly income: ₹{income}", fontsize=14)
            plt.suptitle(f"Monthly Expense Distribution for {month}", fontsize=12)

            chart_path = os.path.join(app.config['UPLOAD_FOLDER'], 'expense_pie.png')
            plt.savefig(chart_path)
            plt.close()

        else:
            alert = "⚠️ No existing expense data found to compare."

        return render_template('ocr.html', text=extracted_text, uploaded_image=file.filename, ocr_total=ocr_total, alert=alert)

# Create the folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def send_alert_email(email, subject, body):
    from email.mime.text import MIMEText
    import smtplib
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'Expense_Alert@gmail.com'
    msg['To'] = email

    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.starttls()
        smtp.login('admin@gmail.com', 'admin123')
        smtp.send_message(msg)

@app.route('/view_expenses')
def view_expenses():
    email = session.get('email')
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT month, income, emi, groceries, utilities, rent, transport, shopping, entertainment, savings, total_expense FROM expenses WHERE email = ?", (email,))
    rows = c.fetchall()
    conn.close()
    return render_template('view_expenses.html', expenses=rows)

@app.route('/month_expenses')
def month_expenses():
    email = session.get('email')
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT month, income, emi, groceries, utilities, rent, transport, shopping, entertainment, savings, receipt,total_expense FROM expenses_bill WHERE email = ?", (email,))
    rows = c.fetchall()
    conn.close()
    return render_template('month_expenses.html', expenses=rows)

@app.route("/get", methods=["POST"])
def get_bot_response():
    msg = request.form["msg"]
    return chatbot_response(msg)

expense_keywords = []
expense_amounts = {}

def chatbot_response(msg):
    global expense_keywords, expense_amounts
    messg = msg.lower()

    expense_categories = ['travel', 'home rent', 'emi', 'loan', 'insurance','savings','buy','purchasing','groceries','expecting','medical expenses']

    for category in expense_categories:
        if category in messg:
            if category not in expense_keywords:
                expense_keywords.append(category)

    rent_match = re.search(r'\b\d+(?:,\d{3})*\b', msg)
    if 'home rent' in messg and rent_match:
        rent_amount = float(rent_match.group().replace(',', '')) 
        expense_amounts['home rent'] = rent_amount
        return f"Is there anything else? Please let me know, or Tell me your salary. I can suggest a plan."

    emi_match = re.search(r'\b\d+(?:,\d{3})*\b', msg)
    if 'emi' in messg and emi_match:
        emi_amount = float(emi_match.group().replace(',',''))
        expense_amounts['emi'] = emi_amount
        return f"Is there anything else? Please let me know, or Tell me your salary. I can suggest a plan."
    
    insurance_match = re.search(r'\b\d+(?:,\d{3})*\b', msg)
    if 'insurance' in messg and insurance_match:
        insurance_amount = float(insurance_match.group().replace(',',''))
        expense_amounts['insurance'] = insurance_amount
        return f"Is there anything else? Please let me know, or Tell me your salary. I can suggest a plan."

    loan_match = re.search(r'\b\d+(?:,\d{3})*\b', msg)
    if 'loan' in messg and loan_match:
        loan_amount = float(loan_match.group().replace(',',''))
        expense_amounts['loan'] = loan_amount
        return f"Is there anything else? Please let me know, or Tell me your salary. I can suggest a plan."

    groceries_match = re.search(r'\b\d+(?:,\d{3})*\b', msg)
    if 'groceries' in messg and groceries_match:
        groceries_amount = float(groceries_match.group().replace(',',''))
        expense_amounts['groceries'] = groceries_amount
        return f"Is there anything else? Please let me know, or Tell me your salary. I can suggest a plan."

    expecting_match = re.search(r'\b\d+(?:,\d{3})*\b', msg)
    if 'expecting' in messg and expecting_match:
        expecting_amount = float(expecting_match.group().replace(',',''))
        expense_amounts['expecting'] = expecting_amount
        return f"Okay, have you already spent money on any other expenses?"

    medical_match = re.search(r'\b\d+(?:,\d{3})*\b', msg)
    if 'medical expenses' in messg and medical_match:
        medical_amount = float(medical_match.group().replace(',',''))
        expense_amounts['medical expenses'] = medical_amount
        return f"Is there anything else? Please let me know, or Tell me your salary. I can suggest a plan."

    salary_match = re.search(r'\b\d+(?:,\d{3})*(?:\.\d{2})?\b', msg)
    if salary_match and 'salary' in messg:
        salary = float(salary_match.group().replace(',', '')) 

        home_rent = expense_amounts.get('home rent', 0)
        emi_rent = expense_amounts.get('emi', 0)
        insurance_rent = expense_amounts.get('insurance', 0)
        loan_rent = expense_amounts.get('loan', 0)
        groceries_rent = expense_amounts.get('groceries', 0)
        expecting_rent = expense_amounts.get('expecting', 0)
        medical_rent = expense_amounts.get('medical expenses', 0)

        remaining_salary = salary - (home_rent + emi_rent + loan_rent + insurance_rent + groceries_rent + expecting_rent + medical_rent)

        if remaining_salary < 0:
            return f"Your salary is not enough to cover the home rent, EMI, loan, and insurance."

        split_ratios = {
            'savings': 0.2 if 'savings' in expense_keywords else 0,  
            'travel': 0.2 if 'travel' in expense_keywords else 0,  
            'Other or Savings':0.4,
        }

        split_ratios = {k: v for k, v in split_ratios.items() if v > 0}
        if not split_ratios:
            return f"Your remaining salary of {remaining_salary:,.2f} is left after covering home rent, EMI, insurance, and loan."

        total_ratio = sum(split_ratios.values())
        split_amounts = {category: round(remaining_salary * (ratio / total_ratio), 2) for category, ratio in split_ratios.items()}

        split_amounts['home rent'] = home_rent
        split_amounts['emi'] = emi_rent
        split_amounts['insurance'] = insurance_rent
        split_amounts['loan'] = loan_rent
        split_amounts['groceries'] = groceries_rent
        split_amounts['expecting'] = expecting_rent
        split_amounts['medical expenses'] = medical_rent
        
        response = f"Your total salary of {salary:,.2f} can be split as follows:\n"
        for category, amt in split_amounts.items():
            response += f"{category}: {amt:,.2f}\n"
        return response
    
    msg_int = int(msg) if msg.isdigit() else None
    if msg_int is not None and 0 <= msg_int <= 99:
        return "Mutual funds in India are required to give a minimum investment value of Rs. 100 for lump-sum deposits and Rs. 500 for Systematic Investment Plans (SIPs) "
    if msg_int is not None and 100 <= msg_int <= 100000000:
        return "Ok, Do you want to invest it on monthly basis or weekly basis?"
    else:
        ints = predict_class(msg, model)
        res = getResponse(ints, intents)
        return res

def clean_up_sentence(sentence):
    sentence_words = nltk.word_tokenize(sentence)
    sentence_words = [lemmatizer.lemmatize(word.lower()) for word in sentence_words]
    return sentence_words

def bow(sentence, words, show_details=True):
    sentence_words = clean_up_sentence(sentence)
    bag = [0] * len(words)
    for s in sentence_words:
        for i, w in enumerate(words):
            if w == s:
                bag[i] = 1
    return np.array(bag)

def predict_class(sentence, model):
    p = bow(sentence, words, show_details=False)
    res = model.predict(np.array([p]))[0]
    ERROR_THRESHOLD = 0.25
    results = [[i, r] for i, r in enumerate(res) if r > ERROR_THRESHOLD]
    results.sort(key=lambda x: x[1], reverse=True)
    return_list = []
    for r in results:
        return_list.append({"intent": classes[r[0]], "probability": str(r[1])})
    return return_list

def getResponse(ints, intents_json):
    if not ints:  
        return "Sorry, I didn't understand that. Could you please clarify?"
    tag = ints[0]["intent"]
    list_of_intents = intents_json["intents"]
    for i in list_of_intents:
        if i["tag"] == tag:
            result = random.choice(i["responses"])
            break
    return result

import webbrowser

if __name__ == "__main__":
    webbrowser.open("http://127.0.0.1:5000")  
    app.run(port=5000)