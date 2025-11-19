
# Simulate what the export should receive
from typing import List, Dict, Any

# Mock data structure
name = "Test_Sample"
dataset = type('obj', (object,), {
    'temperature': 10.0,
    'porosity': 0.40,
    'current_porosity': 0.40,
    'sample_name': 'Test_Sample'
})()

# Mock results - this is what should be coming from dataset_tab.get_results()
results = [
    type('obj', (object,), {
        'method_name': 'Hazen',
        'k_value': 1.23e-4,
        'status': type('obj', (object,), {'value': 'OK'})()
    })(),
    type('obj', (object,), {
        'method_name': 'Kozeny-Carman',
        'k_value': 2.45e-4,
        'status': type('obj', (object,), {'value': 'OK'})()
    })(),
]

print("Testing data structure:")
print(f"Name: {name}")
print(f"Dataset: temperature={dataset.temperature}, porosity={dataset.porosity}")
print(f"Results count: {len(results)}")
for r in results:
    print(f"  - {r.method_name}: {r.k_value} ({r.status.value})")

# Test method lookup
method_results = {}
for result in results:
    method_results[result.method_name] = result

print(f"
Method lookup test:")
print(f"  'Hazen' in method_results: {'Hazen' in method_results}")
print(f"  'Kozeny-Carman' in method_results: {'Kozeny-Carman' in method_results}")
if 'Hazen' in method_results:
    print(f"  Hazen K-value: {method_results['Hazen'].k_value}")
