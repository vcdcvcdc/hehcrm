from flask import Flask, request, jsonify
import json

app = Flask(__name__)
data_file = 'affiliate_data.json'

# Initialize or load data
try:
    with open(data_file, 'r') as file:
        data = json.load(file)
except FileNotFoundError:
    data = {'affiliates': {}, 'total_sales': 0}


def save_data():
    with open(data_file, 'w') as file:
        json.dump(data, file, indent=4)


@app.route('/conversion/<affiliate_id>', methods=['POST'])
def conversion(affiliate_id):
    sale_amount = request.json.get('amount', 0)

    data['total_sales'] += sale_amount

    affiliate_data = next(
        (item for item in data['affiliates'] if item['id'] == affiliate_id), None)

    affiliate_data['sales'] += 1
    affiliate_data['earnings'] += sale_amount * 0.10  # 10% revshare
    save_data()
    return jsonify({'message': 'Conversion recorded', 'affiliate_data': affiliate_data})


@app.route('/stats', methods=['GET'])
def stats():
    return jsonify(data)


@app.route('/reset/<affiliate_id>', methods=['POST'])
def reset(affiliate_id):

    for affiliate in data['affiliates']:
        if affiliate['id'] == affiliate_id:
            print(f"Found Affiliate: {affiliate['earnings']}")
            affiliate['earnings'] = 0
            save_data()
            return jsonify({'message': 'Affiliate payment reset', 'affiliate_id': affiliate_id})
    return jsonify({'message': 'Affiliate not found'}), 404


if __name__ == '__main__':
    app.run(debug=True)
