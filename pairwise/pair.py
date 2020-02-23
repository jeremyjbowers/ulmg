import random
import json

def selectSort(A):
    for i in range(len(A)): 
        
        # Find the minimum element in remaining  
        # unsorted array 
        min_idx = i 
        for j in range(i+1, len(A)): 
            # if A[min_idx] > A[j]:
            print(f'Is \033[1m{A[j][0]}\033[0m better than \033[1m{A[min_idx][0]}\033[0m?')
            text = input()
            if text == "y":
                min_idx = j
                
        # Swap the found minimum element with  
        # the first element         
        A[i], A[min_idx] = A[min_idx], A[i]

    with open('sorted_list.json', 'w') as writefile:
        writefile.write(json.dumps(A))

    print("Okay, here's how you value these players:")
    for i, c in enumerate(A):
        print(f"{i}: {c[0]}")

def bubbleSort(arr): 
    n = len(arr) 
  
    # Traverse through all array elements 
    for i in range(n): 
  
        # Last i elements are already in place 
        for j in range(0, n-i-1): 
  
            # traverse the array from 0 to n-i-1 
            # Swap if the element found is greater 
            # than the next element 
            print(f'Is \033[1m{arr[j+1][0]}\033[0m better than \033[1m{arr[j][0]}\033[0m?')
            text = input()
            if text == "y":
                arr[j], arr[j+1] = arr[j+1], arr[j]

    with open('sorted_list.json', 'w') as writefile:
        writefile.write(json.dumps(arr))

    print("Okay, here's how you value these players:")
    for a in arr:
        print(f"{a[0]}")

def main():
    with open("initial_list.json", 'r') as readfile:
        parameters = [p for p in json.loads(readfile.read())]
    
        selectSort(parameters)

def gen_random_list():
    nums = [z for z in range(1,20)]
    random.shuffle(nums)
    with open('initial_list.json', 'w') as writefile:
        writefile.write(json.dumps(nums))


if __name__ == "__main__":
    main()