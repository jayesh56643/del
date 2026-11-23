
from ultralytics import YOLO
from pathlib import Path

# Get absolute project directory
BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "dataset" / "data.yaml"
SAVE_PATH = BASE_DIR / "runs" / "detect"

# Create output directory
SAVE_PATH.mkdir(parents=True, exist_ok=True)

print("Dataset:", DATA_PATH)
print("Saving training output to:", SAVE_PATH)

# Load pretrained YOLO11
model = YOLO("yolo11n.pt")

# Train
results = model.train(
    data=str(DATA_PATH),
    epochs=100,
    imgsz=512,
    batch=8,
    device="mps",
    workers=4,
    project=str(SAVE_PATH),
    name="yolo11_training",
    patience=10,
    save=True,
    val=True,
    plots=True,
    verbose=True,
    exist_ok=True
)

# Get actual output directory
training_dir = Path(model.trainer.save_dir)

print("\nTraining completed!")
print("Actual save directory:", training_dir.resolve())

# Check model files
best = training_dir / "weights" / "best.pt"
last = training_dir / "weights" / "last.pt"

print("Best model exists:", best.exists())
print("Last model exists:", last.exists())

# Validate the best checkpoint
if best.exists():
    best_model = YOLO(str(best))
    metrics = best_model.val(data=str(DATA_PATH))
    print(metrics)
else:
    print("Best checkpoint not found. Check training logs.")
