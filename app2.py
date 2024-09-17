from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import pandas as pd
import numpy as np
import json
import time
import threading
import queue
from kafka import KafkaConsumer
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler, LabelEncoder
from sklearn.pipeline import Pipeline
import logging

app = Flask(__name__)
socketio = SocketIO(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Kafka consumer
consumer = KafkaConsumer(
    'LapOne',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    value_deserializer=lambda x: x.decode('utf-8')
)

# Load dataset to train models
df = pd.read_csv('hopes2.csv')
df.fillna(0, inplace=True)

# Separate features and targets
X = df.drop(columns=['Location', 'Pit', 'PitCompound'])
y_pit = df['Pit']
y_compound = df['PitCompound']

# Encode the PitCompound target variable
label_encoder = LabelEncoder()
y_compound_encoded = label_encoder.fit_transform(y_compound)

# Define the column transformer for preprocessing
preprocessor = ColumnTransformer(
    transformers=[
        ('onehot', OneHotEncoder(), ['Compound']),
        ('scale', StandardScaler(), ['LapTime', 'LapNumber', 'Stint', 'Sector1Time', 'Sector2Time', 'Sector3Time', 
                                     'SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST', 'TyreLife', 'TrackStatus', 'Position'])
    ],
    remainder='passthrough'
)

# Train the models
def train_models():
    # XGBoost for Pit
    xgb_model_pit = xgb.XGBClassifier(
        objective='binary:logistic',
        random_state=42,
        colsample_bytree=0.9,
        learning_rate=0.2,
        max_depth=5,
        n_estimators=300,
        subsample=0.9
    )

    # Random Forest for Pit
    rf_model_pit = RandomForestClassifier(
        random_state=42,
        max_depth=20,
        min_samples_leaf=1,
        min_samples_split=2,
        n_estimators=100
    )

    # Random Forest for PitCompound
    rf_model_compound = RandomForestClassifier(
        random_state=42,
        max_depth=None,
        min_samples_leaf=1,
        min_samples_split=2,
        n_estimators=100
    )

    # XGBoost for PitCompound
    xgb_model_compound = xgb.XGBClassifier(
        objective='multi:softmax',
        random_state=42,
        colsample_bytree=0.8,
        learning_rate=0.2,
        max_depth=5,
        n_estimators=200,
        subsample=1.0
    )

    # Train pipelines
    xgb_model_pit_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', xgb_model_pit)
    ])
    xgb_model_pit_pipeline.fit(X, y_pit)

    rf_model_pit_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', rf_model_pit)
    ])
    rf_model_pit_pipeline.fit(X, y_pit)

    rf_model_compound_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', rf_model_compound)
    ])
    rf_model_compound_pipeline.fit(X, y_compound_encoded)

    xgb_model_compound_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', xgb_model_compound)
    ])
    xgb_model_compound_pipeline.fit(X, y_compound_encoded)

    return rf_model_pit_pipeline, xgb_model_pit_pipeline, rf_model_compound_pipeline, xgb_model_compound_pipeline

# Train the models and get the pipelines
rf_classifier_pit, xgb_classifier_pit, rf_classifier_compound, xgb_classifier_compound = train_models()

# Create queues to hold the data
position_data_queue = queue.Queue()
laptime_data_queue = queue.Queue()
sector_data_queue = queue.Queue()
compound_data_queue = queue.Queue()
data_queue = queue.Queue()

# Function to consume messages from Kafka and put them in the appropriate queues
def consume_kafka():
    try:
        for message in consumer:
            data = json.loads(message.value)
            lap_number = int(data.get('LapNumber', 0))
            position = int(data.get('Position', 0))
            lap_time = float(data.get('LapTime', 0))
            sector1_time = float(data.get('Sector1Time', 0))
            sector2_time = float(data.get('Sector2Time', 0))
            sector3_time = float(data.get('Sector3Time', 0))
            compound = data.get('Compound', '')

            position_data_queue.put((lap_number, position))
            laptime_data_queue.put((lap_number, lap_time))
            sector_data_queue.put((lap_number, sector1_time, sector2_time, sector3_time))
            compound_data_queue.put((lap_number, lap_time, compound))
            data_queue.put(data)

            logger.info("Consumed: %s", data)
            time.sleep(2)
    except Exception as e:
        logger.error("Error consuming Kafka message: %s", e)
    finally:
        consumer.close()
        logger.info("Kafka consumer closed.")

# Start the Kafka consumer in a separate thread
consumer_thread = threading.Thread(target=consume_kafka)
consumer_thread.daemon = True
consumer_thread.start()

# Function to make predictions
def make_predictions(model, X):
    predictions = model.predict(X)
    return predictions

# Function to send data to the client
def send_data():
    while True:
        try:
            while not position_data_queue.empty():
                lap_number, position = position_data_queue.get()
                socketio.emit('update_position', {'lap_number': lap_number, 'position': position})
        
            while not laptime_data_queue.empty():
                lap_number, lap_time = laptime_data_queue.get()
                socketio.emit('update_laptime', {'lap_number': lap_number, 'lap_time': lap_time})
        
            while not sector_data_queue.empty():
                lap_number, sector1_time, sector2_time, sector3_time = sector_data_queue.get()
                socketio.emit('update_sector', {
                    'lap_number': lap_number, 
                    'sector1_time': sector1_time, 
                    'sector2_time': sector2_time, 
                    'sector3_time': sector3_time
                })
        
            while not compound_data_queue.empty():
                lap_number, lap_time, compound = compound_data_queue.get()
                socketio.emit('update_compound', {'lap_number': lap_number, 'lap_time': lap_time, 'compound': compound})
        
            while not data_queue.empty():
                data = data_queue.get()
                lap_number = int(data.get('LapNumber', 0))

                # Ensure the incoming data is in DataFrame format and drop unnecessary columns
                data_df = pd.DataFrame([data])
                data_df.fillna(0, inplace=True)

                # Drop columns that were not used in training
                X = data_df.drop(columns=['Location', 'Pit', 'PitCompound'])

                # Explicitly select the features used during training
                features_used_in_training = [
                    'LapTime', 'LapNumber', 'Stint', 'Sector1Time', 'Sector2Time',
                    'Sector3Time', 'SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST',
                    'Compound', 'TyreLife', 'TrackStatus', 'Position'
                ]
                X = X[features_used_in_training]

                # Apply preprocessing and prediction
                X_transformed = preprocessor.transform(X)

                # Predicting Pit and PitCompound
                rf_pit_prediction = rf_classifier_pit.predict(X_transformed)[0]
                xgb_pit_prediction = xgb_classifier_pit.predict(X_transformed)[0]
                
                rf_compound_prediction = rf_classifier_compound.predict(X_transformed)[0]
                xgb_compound_prediction = xgb_classifier_compound.predict(X_transformed)[0]

                # Convert compound predictions back to original labels
                rf_compound_label = label_encoder.inverse_transform([rf_compound_prediction])[0]
                xgb_compound_label = label_encoder.inverse_transform([xgb_compound_prediction])[0]

                # Emit predictions
                socketio.emit('update_predictions', {
                    'LapNumber': lap_number,
                    'RF_Pit_Predictions': int(rf_pit_prediction),  # Ensure Pit is treated as an integer
                    'XGB_Pit_Predictions': int(xgb_pit_prediction),  # Ensure Pit is treated as an integer
                    'RF_Compound_Predictions': rf_compound_label,  # Text output
                    'XGB_Compound_Predictions': xgb_compound_label  # Text output
                })
                logger.info(f"Sent predictions: LapNumber={lap_number}, RF_Pit={rf_pit_prediction}, XGB_Pit={xgb_pit_prediction}, RF_Compound={rf_compound_label}, XGB_Compound={xgb_compound_label}")

            time.sleep(1)
        except Exception as e:
            logger.error("Error sending data: %s", e)

# Start the data sending in a separate thread
send_data_thread = threading.Thread(target=send_data)
send_data_thread.daemon = True
send_data_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    try:
        socketio.run(app, debug=True)
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully.")
        consumer_thread.join()
        send_data_thread.join()
        logger.info("Application stopped.")
