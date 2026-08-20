import sounddevice as sd


print("=" * 50)
print("SERA MICROPHONE TEST")
print("=" * 50)

print("\nAvailable audio devices:\n")

devices = sd.query_devices()

for index, device in enumerate(devices):
    print(
        f"[{index}] "
        f"{device['name']} "
        f"(inputs={device['max_input_channels']}, "
        f"outputs={device['max_output_channels']})"
    )

print("\nDefault input device:")

default_input = sd.default.device[0]

print(f"Index: {default_input}")

if default_input is not None:
    print(
        f"Name: {devices[default_input]['name']}"
    )