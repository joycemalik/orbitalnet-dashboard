from sgp4.api import Satrec, jday
import redis
import time
from datetime import datetime

# Connect to local Redis
r = redis.Redis(host='localhost', port=6379, db=0)

def load_satellites(filepath):
    satellites = {}
    with open(filepath, 'r') as f:
        lines = f.readlines()
        # Parse TLEs in chunks of 3: Name, Line 1, Line 2
        for i in range(0, len(lines), 3):
            if i+2 < len(lines):
                name = lines[i].strip()
                line1 = lines[i+1].strip()
                line2 = lines[i+2].strip()
                # Create SGP4 satellite object
                satrec = Satrec.twoline2rv(line1, line2)
                satellites[name] = satrec
    return satellites

def start_engine():
    fleet = load_satellites('satellites.txt')
    print(f"Loaded {len(fleet)} satellites. Booting SGP4 engine...")
    
    while True:
        now = datetime.utcnow()
        # SGP4 requires Julian Date
        jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute, now.second)
        
        # Pipeline batches Redis commands for massive speed
        pipe = r.pipeline()
        
        for name, sat in fleet.items():
            # e is error code, position is (X, Y, Z) in km
            e, position, velocity = sat.sgp4(jd, fr)
            
            if e == 0:
                # Store coordinates as a string in Redis
                coord_str = f"{position[0]},{position[1]},{position[2]}"
                pipe.set(name, coord_str)
                
        pipe.execute()
        time.sleep(1) # Update at 1 Hertz

if __name__ == '__main__':
    start_engine()
