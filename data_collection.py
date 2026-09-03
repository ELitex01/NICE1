import pandas as pd
import numpy as np
def merge_csv(input):
    if(input=="train"):
        train_1 = pd.read_csv("Data/Train_1.csv")
        for i in range(2, 11):
            t = pd.read_csv(f"Data/Train_{i}.csv")
            train_1 = pd.concat((train_1, t), ignore_index=True)
        return train_1  # <--- Un-indented outside the loop

    if(input=="test"):
        test_1 = pd.read_csv("Data/Test_1.csv")
        for i in range(2, 11):
            t = pd.read_csv(f"Data/Test_{i}.csv")
            test_1 = pd.concat((test_1, t), ignore_index=True)
        return test_1   # <--- Un-indented outside the loop

    return 0