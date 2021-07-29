# PseudoCode for Tap.py
# Import Core Libraries
import HuskyLens
import Arduino

ObjectID = HuskyLens.GetObjectID()  # Get the current object ID

ObjectDictionary = {                # Maps to object identity from ID
    0: "NONE",
    1: "ToothBrush",
    2: "Apple",
    3: "Carrot",
    4: "Hand"
}

CurrentWaterVolume = [              # Current state of learned water volume. Read as: [percentage open, time open]
    [0,0],[20,5],[70,7],[60,7],[80,15]
]

MinWaterVolume = [                  # Minimum water volume for each object. Read as: [percentage open, time open]
    [0,0],[10,2],[40,5],[40,5],[70,15]
]

# Function that updates and decrease water volume use if user doesn't use the full allocated volume
def UpdateWaterVolume(ObjectID, NewVolume): 
    CurrentWaterVolume(ObjectID) = min(MinWaterVolume(ObjectID), 0.2*NewVolume + 0.8*CurrentWaterVolume(ObjectID))
    return CurrentWaterVolume(ObjectID)

# Open the water if something is being presented and permits volume according to ObjectID
while ObjectID != 0:
    State = Arduino.RotateValve(CurrentWaterVolume(ObjectID))

# If the users stop using the water to full allocated amount, close the tap and reduce the volume
if ObjectID == 0 & State != 0:
    Arduino.CloseValve()
    CurrentWaterVolume(Arduino.LastObjectID) = UpdateWaterVolume(Arduino.LastObjectID, Arduino.LastObjectVolume)

# :) Save Water!!