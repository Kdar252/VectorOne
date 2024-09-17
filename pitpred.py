import pandas as pd
import numpy as np
import pickle
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb
from confluent_kafka import Consumer, KafkaException

# Load the saved ColumnTransformer
with open('C:/Users/kedar/OneDrive/Desktop/f1 race/f1 race/column_transformer.pkl', 'rb') as f:
    ct = pickle.load(f)

# Load the saved Random Forest model
with open('rf_classifier_pit.pkl', 'rb') as f:
    rf_classifier = pickle.load(f)

# Load the saved XGBoost model
with open('xgb_classifier.pkl', 'rb') as f:
    xgb_classifier = pickle.load(f)

# Function to make predictions
def make_predictions(model, X):
    predictions = model.predict(X)
    return predictions

# Kafka consumer configuration
conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'my_consumer_group',
    'auto.offset.reset': 'earliest'
}

consumer = Consumer(conf)
topic = "your_kafka_topic"
consumer.subscribe([topic])

print("Starting Kafka consumer...")

try:
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                print('End of partition reached {0}/{1}'.format(msg.topic(), msg.partition()))
            elif msg.error():
                raise KafkaException(msg.error())
        else:
            # Process the message
            msg_value = msg.value().decode('utf-8')
            data = pd.read_json(msg_value)  # Assuming the Kafka message is a JSON string

            # Fill NaN values and drop extra columns to match the features used for training
            data.fillna(0, inplace=True)
            data = data.drop(columns=['Location', 'Pit', 'PitCompound'])

            # Transform the data
            X_external = np.array(ct.transform(data.values))

            # Make predictions using Random Forest
            rf_predictions = make_predictions(rf_classifier, X_external)
            data['RF_Predictions'] = rf_predictions

            # Make predictions using XGBoost
            xgb_predictions = make_predictions(xgb_classifier, X_external)
            data['XGB_Predictions'] = xgb_predictions

            # Print the predictions or handle them as needed
            print(data[['RF_Predictions', 'XGB_Predictions']])
finally:
    consumer.close()
