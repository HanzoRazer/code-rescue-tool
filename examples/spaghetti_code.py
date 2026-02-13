"""
Example of spaghetti code with various code smells.
This file is intentionally bad for demonstration purposes.
"""

import os
import sys
import json
import random
import time
from typing import List, Dict
from collections import defaultdict


def process_user_data(user_id, name, email, age, address, phone, city, state, zip_code, country, preferences):
    """A function with too many parameters."""
    # Process user data
    result = {
        'id': user_id,
        'name': name,
        'email': email,
        'age': age,
        'address': address,
        'phone': phone,
        'city': city,
        'state': state,
        'zip': zip_code,
        'country': country,
        'preferences': preferences,
    }
    return result


def deeply_nested_function(data):
    """A function with excessive nesting depth."""
    if data:
        if isinstance(data, dict):
            if 'users' in data:
                for user in data['users']:
                    if user.get('active'):
                        if user.get('age', 0) > 18:
                            if user.get('verified'):
                                if user.get('premium'):
                                    # Do something at depth 7
                                    print(f"Processing premium user: {user['name']}")
                                    return True
    return False


def very_long_function_with_lots_of_code(input_data):
    """
    This is an extremely long function that does way too much.
    It should be broken down into smaller, more focused functions.
    """
    # Initialize variables
    result = {}
    errors = []
    warnings = []
    processed_count = 0
    
    # Validate input
    if not input_data:
        errors.append("No input data provided")
        return {'errors': errors}
    
    # Check if input is a list
    if not isinstance(input_data, list):
        errors.append("Input must be a list")
        return {'errors': errors}
    
    # Process each item
    for item in input_data:
        try:
            # Validate item structure
            if not isinstance(item, dict):
                warnings.append(f"Skipping non-dict item: {item}")
                continue
            
            # Extract fields
            item_id = item.get('id')
            item_name = item.get('name')
            item_value = item.get('value')
            item_type = item.get('type')
            item_status = item.get('status')
            
            # Validate required fields
            if not item_id:
                warnings.append("Item missing ID")
                continue
            
            if not item_name:
                warnings.append(f"Item {item_id} missing name")
                continue
            
            # Process based on type
            if item_type == 'A':
                # Type A processing
                processed_value = item_value * 2
                if processed_value > 100:
                    processed_value = 100
                result[item_id] = {
                    'name': item_name,
                    'value': processed_value,
                    'type': item_type,
                    'status': 'processed'
                }
            elif item_type == 'B':
                # Type B processing
                processed_value = item_value + 10
                if processed_value < 0:
                    processed_value = 0
                result[item_id] = {
                    'name': item_name,
                    'value': processed_value,
                    'type': item_type,
                    'status': 'processed'
                }
            elif item_type == 'C':
                # Type C processing
                processed_value = item_value / 2
                result[item_id] = {
                    'name': item_name,
                    'value': processed_value,
                    'type': item_type,
                    'status': 'processed'
                }
            else:
                warnings.append(f"Unknown type for item {item_id}: {item_type}")
                continue
            
            processed_count += 1
            
        except Exception as e:
            errors.append(f"Error processing item: {str(e)}")
            continue
    
    # Generate summary
    summary = {
        'total_items': len(input_data),
        'processed': processed_count,
        'errors': len(errors),
        'warnings': len(warnings)
    }
    
    # Return results
    return {
        'results': result,
        'summary': summary,
        'errors': errors,
        'warnings': warnings
    }


class VeryLargeClass:
    """A class with too many methods and responsibilities."""
    
    def __init__(self, config):
        self.config = config
        self.data = {}
        self.cache = {}
        self.stats = defaultdict(int)
    
    def method1(self):
        return "method1"
    
    def method2(self):
        return "method2"
    
    def method3(self):
        return "method3"
    
    def method4(self):
        return "method4"
    
    def method5(self):
        return "method5"
    
    def method6(self):
        return "method6"
    
    def method7(self):
        return "method7"
    
    def method8(self):
        return "method8"
    
    def method9(self):
        return "method9"
    
    def method10(self):
        return "method10"
    
    def method11(self):
        return "method11"
    
    def method12(self):
        return "method12"
    
    def method13(self):
        return "method13"
    
    def method14(self):
        return "method14"
    
    def method15(self):
        return "method15"
    
    def another_very_long_method(self):
        """Another long method that does too much."""
        # Initialize
        results = []
        temp_data = {}
        
        # Process data
        for key, value in self.data.items():
            if value:
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if sub_value:
                            temp_data[f"{key}_{sub_key}"] = sub_value
                            results.append(sub_value)
        
        # More processing
        processed = []
        for item in results:
            if item > 0:
                processed.append(item * 2)
            else:
                processed.append(item)
        
        # Even more processing
        final = []
        for val in processed:
            if val > 100:
                final.append(100)
            elif val < 0:
                final.append(0)
            else:
                final.append(val)
        
        return final


def high_complexity_function(x, y, z):
    """A function with high cyclomatic complexity."""
    result = 0
    
    if x > 0:
        result += 1
    elif x < 0:
        result -= 1
    
    if y > 0:
        result += 2
    elif y < 0:
        result -= 2
    
    if z > 0:
        result += 3
    elif z < 0:
        result -= 3
    
    if x > y:
        result *= 2
    elif x < y:
        result /= 2
    
    if y > z:
        result += 10
    elif y < z:
        result -= 10
    
    if x + y > z:
        result += 5
    elif x + y < z:
        result -= 5
    
    return result


def another_high_complexity_function(a, b, c):
    """Another function with high cyclomatic complexity."""
    result = 0
    
    if a > 0:
        result += 1
    elif a < 0:
        result -= 1
    
    if b > 0:
        result += 2
    elif b < 0:
        result -= 2
    
    if c > 0:
        result += 3
    elif c < 0:
        result -= 3
    
    if a > b:
        result *= 2
    elif a < b:
        result /= 2
    
    if b > c:
        result += 10
    elif b < c:
        result -= 10
    
    if a + b > c:
        result += 5
    elif a + b < c:
        result -= 5
    
    return result


if __name__ == '__main__':
    # Test the spaghetti code
    test_data = [
        {'id': 1, 'name': 'Item 1', 'value': 50, 'type': 'A', 'status': 'active'},
        {'id': 2, 'name': 'Item 2', 'value': 30, 'type': 'B', 'status': 'active'},
    ]
    
    result = very_long_function_with_lots_of_code(test_data)
    print(json.dumps(result, indent=2))
