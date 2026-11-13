from flask import Flask, request, jsonify, render_template
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
@app.route("/")
def home():
    return render_template ("index.html")
@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json()

    num1 = float(data["num1"])
    num2 = float(data["num2"])
    operator = data["operator"]

    if operator == "+":
        result = num1 + num2

    elif operator == "-":
        result = num1 - num2

    elif operator == "*":
        result = num1 * num2

    elif operator == "/":
        if num2 == 0:
            return jsonify({"error": "Cannot divide by zero"}), 400
        result = num1 / num2

    else:
        return jsonify({"error": "Invalid operator"}), 400

    return jsonify({"result": result})
if __name__ == "__main__":
    app.run(port=5001, debug=True)