from flask import Flask, request, jsonify
import json
import stripe
from datetime import datetime, timedelta
import atexit
from apscheduler.schedulers.background import BackgroundScheduler

# from flask_restful import Resource, Api
# from apispec import APISpec
# from marshmallow import Schema, fields
# from apispec.ext.marshmallow import MarshmallowPlugin
# from flask_apispec.extension import FlaskApiSpec
# from flask_apispec.views import MethodResource
# from flask_apispec import marshal_with, doc, use_kwargs

app = Flask(__name__)
# api = Api(app)  # Flask restful wraps Flask app around it.

# app.config.update({
#     'APISPEC_SPEC': APISpec(
#         title='Awesome Project',
#         version='v1',
#         plugins=[MarshmallowPlugin()],
#         openapi_version='2.0.0'
#     ),
#     'APISPEC_SWAGGER_URL': '/swagger/',  # URI to access API Doc JSON
#     'APISPEC_SWAGGER_UI_URL': '/swagger-ui/'  # URI to access UI of API Doc
# })
# docs = FlaskApiSpec(app)


data_file = 'affiliate_data.json'
stripe.api_key = 'your_stripe_api_key'
stripe_webhook_secret = 'your_stripe_webhook_secret'

# Initialize or load data
try:
    with open(data_file, 'r') as file:
        data = json.load(file)
except FileNotFoundError:
    # data = {'affiliates': {}, 'total_sales': 0}
    data = {'affiliates': {}, 'total_sales': 0,
            'last_checked': datetime.now().isoformat()}


def save_data():
    with open(data_file, 'w') as file:
        json.dump(data, file, indent=4)


def check_cancellations():
    last_checked = datetime.fromisoformat(data['last_checked'])
    cancellations = stripe.Refund.list(
        created={'gte': last_checked.timestamp()})
    for refund in cancellations.auto_paging_iter():
        affiliate_id = refund.metadata.get('affiliate_id')

        for affiliate in data['affiliates']:
            if affiliate['id'] == affiliate_id:
                refund_amount = refund.amount / 100  # Convert from cents to dollars
                affiliate['earnings'] -= refund_amount * 0.10

    data['last_checked'] = datetime.now().isoformat()
    save_data()


scheduler = BackgroundScheduler()
scheduler.add_job(func=check_cancellations, trigger="interval", days=1)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())


@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_webhook_secret
        )
    except ValueError:
        # Invalid payload
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return 'Invalid signature', 400

    # Handle the event
    if event['type'] == 'charge.succeeded':
        charge = event['data']['object']
        affiliate_id = charge.metadata.get('affiliate_id')

        for affiliate in data['affiliates']:
            if affiliate['id'] == affiliate_id:

                sale_amount = charge.amount / 100  # Convert from cents to dollars
                affiliate['earnings'] += sale_amount * 0.10  # 10% revshare
                save_data()

    return '', 200


# class ConversionResponseSchema(Schema):
#     message = fields.Str(default='Success')


# class ConversionRequestSchema(Schema):
#     api_type = fields.Number(
#         required=True, description="API type of awesome API")


# class ConversionAPI(MethodResource, Resource):

#     @doc(description='My First POST Conversion API.', tags=['Conversion'])
#     @use_kwargs(ConversionRequestSchema, location=('json'))
#     @marshal_with(ConversionResponseSchema)  # marshalling
#     def post(self, **affiliate_id):
#         '''
#         POST method represents a POST API method
#         '''
#         # return affiliate_id
#         return {'message': affiliate_id}

#         sale_amount = request.json.get('amount', 0)

#         data['total_sales'] += sale_amount

#         affiliate_data = next(
#             (item for item in data['affiliates'] if item['id'] == affiliate_id), None)

#         affiliate_data['sales'] += 1
#         affiliate_data['earnings'] += sale_amount * 0.10  # 10% revshare
#         save_data()
#         return jsonify({'message': 'Conversion recorded', 'affiliate_data': affiliate_data})


# api.add_resource(ConversionAPI, '/conversion/{affiliate_id}')
# docs.register(ConversionAPI)


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


@app.route('/pay/<affiliate_id>', methods=['POST'])
def pay_affiliate(affiliate_id):
    for affiliate in data['affiliates']:
        if affiliate['id'] == affiliate_id:
            amount = affiliate['earnings']
            affiliate['payments'].append(amount)
            affiliate['earnings'] = 0
            save_data()
            return jsonify({'message': 'Affiliate paid', 'amount': amount, 'affiliate_id': affiliate_id})
    return jsonify({'message': 'Affiliate not found'}), 404


if __name__ == '__main__':
    app.run(debug=True)
