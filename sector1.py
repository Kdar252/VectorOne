import json
import time
import threading
import queue
from kafka import KafkaConsumer
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Initialize Kafka consumer
consumer = KafkaConsumer(
    'LapOne',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    value_deserializer=lambda x: x.decode('utf-8')
)

# Create queues to hold the data
position_data_queue = queue.Queue()
laptime_data_queue = queue.Queue()
sector_data_queue = queue.Queue()
compound_data_queue = queue.Queue()

# Function to consume messages from Kafka and put them in the appropriate queues
def consume_kafka():
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
        
        print("Consumed:", data)
        time.sleep(2)

# Start the Kafka consumer in a separate thread
consumer_thread = threading.Thread(target=consume_kafka)
consumer_thread.daemon = True
consumer_thread.start()

# Lists to store the data
lap_numbers_positions = []
positions = []

lap_numbers_laptimes = []
lap_times = []

lap_numbers_sectors = []
sector1_times = []
sector2_times = []
sector3_times = []

lap_numbers_compounds = []
lap_times_compounds = []
compounds = []

# Color map for tire compounds
compound_colors = {
    'SOFT': 'red',
    'MEDIUM': 'yellow',
    'HARD': 'grey',
    'INTERMEDIATE': 'blue',
    'WET': 'green'
}

# Function to update the position plot
def update_positions(frame):
    while not position_data_queue.empty():
        lap_number, position = position_data_queue.get()
        lap_numbers_positions.append(lap_number)
        positions.append(position)
    
    ax1.cla()
    ax1.plot(lap_numbers_positions, positions, marker='o')
    ax1.set_xlabel('Lap Number')
    ax1.set_ylabel('Position')
    ax1.set_title('Real-Time Race Positions')
    ax1.grid(True)
    ax1.set_xlim(0, max(lap_numbers_positions) + 1 if lap_numbers_positions else 1)
    ax1.set_ylim(0, max(positions) + 1 if positions else 1)
    ax1.set_xticks(range(0, max(lap_numbers_positions) + 1 if lap_numbers_positions else 1, 1))
    ax1.set_yticks(range(0, max(positions) + 1 if positions else 1, 1))

# Function to update the lap times plot
def update_laptimes(frame):
    while not laptime_data_queue.empty():
        lap_number, lap_time = laptime_data_queue.get()
        lap_numbers_laptimes.append(lap_number)
        lap_times.append(lap_time)
    
    ax2.cla()
    ax2.plot(lap_numbers_laptimes, lap_times, marker='o')
    ax2.set_xlabel('Lap Number')
    ax2.set_ylabel('Lap Time (seconds)')
    ax2.set_title('Real-Time Lap Times')
    ax2.grid(True)
    ax2.set_xlim(0, max(lap_numbers_laptimes) + 1 if lap_numbers_laptimes else 1)
    ax2.set_ylim(0, max(lap_times) + 5 if lap_times else 5)
    ax2.set_xticks(range(0, max(lap_numbers_laptimes) + 1 if lap_numbers_laptimes else 1, 1))
    ax2.set_yticks(range(0, int(max(lap_times)) + 5 if lap_times else 5, 5))

# Function to update the sector times plot
def update_sectors(frame):
    while not sector_data_queue.empty():
        lap_number, sector1_time, sector2_time, sector3_time = sector_data_queue.get()
        lap_numbers_sectors.append(lap_number)
        sector1_times.append(sector1_time)
        sector2_times.append(sector2_time)
        sector3_times.append(sector3_time)
    
    ax3.cla()
    ax3.plot(lap_numbers_sectors, sector1_times, marker='o', color='blue', label='Sector 1')
    ax3.plot(lap_numbers_sectors, sector2_times, marker='o', color='green', label='Sector 2')
    ax3.plot(lap_numbers_sectors, sector3_times, marker='o', color='red', label='Sector 3')
    ax3.set_xlabel('Lap Number')
    ax3.set_ylabel('Sector Time (seconds)')
    ax3.set_title('Real-Time Sector Times by Lap Number')
    ax3.grid(True)
    ax3.set_xlim(0, max(lap_numbers_sectors) + 1 if lap_numbers_sectors else 1)
    ax3.set_ylim(0, max(max(sector1_times, default=0), max(sector2_times, default=0), max(sector3_times, default=0)) + 5)
    ax3.set_xticks(range(0, max(lap_numbers_sectors) + 1 if lap_numbers_sectors else 1, 1))
    ax3.set_yticks(range(0, int(max(max(sector1_times, default=0), max(sector2_times, default=0), max(sector3_times, default=0))) + 5, 5))
    ax3.legend()

# Function to update the lap times plot with tire compounds
def update_compounds(frame):
    while not compound_data_queue.empty():
        lap_number, lap_time, compound = compound_data_queue.get()
        lap_numbers_compounds.append(lap_number)
        lap_times_compounds.append(lap_time)
        compounds.append(compound)
    
    ax4.cla()
    for compound, color in compound_colors.items():
        compound_lap_numbers = [lap_numbers_compounds[i] for i in range(len(lap_numbers_compounds)) if compounds[i] == compound]
        compound_lap_times = [lap_times_compounds[i] for i in range(len(lap_times_compounds)) if compounds[i] == compound]
        ax4.plot(compound_lap_numbers, compound_lap_times, marker='o', color=color, label=compound)
    
    ax4.set_xlabel('Lap Number')
    ax4.set_ylabel('Lap Time (seconds)')
    ax4.set_title('Real-Time Lap Times by Tire Compound')
    ax4.grid(True)
    ax4.set_xlim(0, max(lap_numbers_compounds) + 1 if lap_numbers_compounds else 1)
    ax4.set_ylim(0, max(lap_times_compounds) + 5 if lap_times_compounds else 5)
    ax4.set_xticks(range(0, max(lap_numbers_compounds) + 1 if lap_numbers_compounds else 1, 1))
    ax4.set_yticks(range(0, int(max(lap_times_compounds)) + 5 if lap_times_compounds else 5, 5))
    ax4.legend()

# Set up the figure and axes
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

# Create the animations
ani_positions = FuncAnimation(fig, update_positions, interval=1000)
ani_laptimes = FuncAnimation(fig, update_laptimes, interval=1000)
ani_sectors = FuncAnimation(fig, update_sectors, interval=1000)
ani_compounds = FuncAnimation(fig, update_compounds, interval=1000)

# Continuously save the animations as GIFs
def save_gifs():
    while True:
        ani_positions.save('animation1.gif', writer='imagemagick')
        ani_laptimes.save('animation2.gif', writer='imagemagick')
        ani_sectors.save('animation3.gif', writer='imagemagick')
        ani_compounds.save('animation4.gif', writer='imagemagick')
        time.sleep(10)

# Start saving the GIFs in a separate thread
gif_thread = threading.Thread(target=save_gifs)
gif_thread.daemon = True
gif_thread.start()

# Keep the script running
plt.show()