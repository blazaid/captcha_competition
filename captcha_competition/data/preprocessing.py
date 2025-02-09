import numpy as np
import cv2
import torch
from captcha_competition.data.generate_captcha import generate_captcha_image
import matplotlib.pyplot as plt
from collections import Counter
import torch
import torch.functional as F

TENSOR_TYPE = torch.float32
NUM_NUMBERS = 6


############ Preprocessing Type 1 ############


def most_common_colors(img, n=1):
    unique, counts = np.unique(img.reshape(-1, 3), axis=0, return_counts=True)
    return unique[np.argsort(counts)[-n]], counts[np.argsort(counts)[-n]]


def get_bg_color(img):
    top = img[: int(img.shape[0] / 4)]
    bottom = img[int(img.shape[0] * 3 / 4) :]
    top_color, top_count = most_common_colors(top)
    bottom_color, bottom_count = most_common_colors(bottom)
    if top_count > bottom_count:
        return top_color

    return bottom_color


def remove_bg(img, grayscale=True):
    bg_color = get_bg_color(img)
    first_color, _ = most_common_colors(img, n=1)
    second_color, _ = most_common_colors(img, n=2)
    if np.all(first_color == bg_color):
        num_color = second_color
    else:
        num_color = first_color
    mask = np.all(img == num_color, axis=-1)
    mask = np.stack([mask, mask, mask], axis=-1)
    new_img = img * mask
    if grayscale:
        new_img = cv2.cvtColor(new_img, cv2.COLOR_BGR2GRAY)
        new_img = cv2.convertScaleAbs(new_img)
    return new_img


############ Preprocessing Type 2 ############


def cleaned_image(image: np.ndarray, kernel_size=2) -> np.ndarray:

    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Binarize
    # Top most left pixel is the background color
    background_color = image[0, 0]
    # If the background color is dark and the text is light
    if background_color < 128:
        ret, binary = cv2.threshold(
            image, background_color, 255, cv2.THRESH_BINARY
        )
    # If the background color is light and the text is dark
    else:
        ret, binary = cv2.threshold(
            image, background_color - 1, 255, cv2.THRESH_BINARY_INV
        )

    # Close the image: dilate and then erode to remove dots and lines
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    dilated = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel)

    return cleaned


############ Preprocessing Type 3 ############


def best_of_both_worlds(image: np.ndarray, kernel_size=5) -> np.ndarray:

    # Best of preprocessing type 1
    image = remove_bg(image)
    # Best of preprocessing type 2
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    eroded = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
    return eroded


############ Preprocessing Type 4 ############


def preprocessing(image: np.ndarray, kernel_size=5) -> np.ndarray:

    # Convert the image to grayscale
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Divide the image into 10x10 windows.
    windows = np.lib.stride_tricks.as_strided(
        image,
        shape=(image.shape[0] // 10, image.shape[1] // 10, 10, 10),
        strides=(image.shape[1] * 10, 10, image.shape[1], 1),
    )
    # Calculate the most common color in each window.
    color_counter = np.array([Counter(window.flatten()) for window in windows])
    # Calculate the most common color in the image.
    color_mode = [
        value for value, frequency in color_counter.sum(axis=0).most_common(2)
    ]
    # Copy the image
    new_image = np.copy(image)
    # Change everything that is not the second most common color (text) to the first most common color (background)
    new_image[(new_image != color_mode[1])] = color_mode[0]
    # Convert the image to binary
    if color_mode[0] > color_mode[1]:
        _, new_image = cv2.threshold(
            new_image, color_mode[0], 255, cv2.THRESH_BINARY
        )
    else:
        _, new_image = cv2.threshold(
            new_image, color_mode[0], 255, cv2.THRESH_BINARY_INV
        )
    # Return the binarized image
    return new_image


def preprocessing_tensor(image: torch.Tensor) -> torch.Tensor:
    # Convert the image to grayscale
    image = torch.mean(image, dim=2, keepdim=True)

    # Divide the image into 10x10 windows.
    windows = image.unfold(0, 10, 10).unfold(1, 10, 10)

    # Reshape windows to match numpy's behavior
    windows = windows.permute(0, 1, 3, 4, 2).reshape(-1, 10, 10)

    # Calculate the most common color in each window.
    color_counter = torch.tensor(
        [torch.bincount(window.flatten(), minlength=256) for window in windows]
    )

    # Calculate the most common color in the image.
    color_mode = torch.tensor(
        [value for value, _ in torch.sum(color_counter, dim=0).topk(2)[0]]
    )

    # Copy the image
    new_image = image.clone()

    # Change everything that is not the second most common color (text) to the first most common color (background)
    new_image[new_image != color_mode[1]] = color_mode[0]

    # Convert the image to binary
    threshold_value = (
        color_mode[0] if color_mode[0] > color_mode[1] else color_mode[1]
    )
    new_image = torch.where(
        new_image > threshold_value, torch.tensor(255), torch.tensor(0)
    ).byte()

    return new_image


############ Testing ############

if __name__ == "__main__":
    import matplotlib.pyplot as plt

    image_, label_ = generate_captcha_image()
    new_image = remove_bg(image_)
    new_image2 = cleaned_image(image_)
    new_image3 = best_of_both_worlds(image_)
    new_image4 = preprocessing(image_)

    plt.figure(figsize=(10, 6))

    plt.subplot(151), plt.imshow(image_, cmap="gray")
    plt.title("Original Image")
    plt.xticks([]), plt.yticks([])

    plt.subplot(152), plt.imshow(new_image, cmap="gray")
    plt.title("Preprocessed Mode 1")
    plt.xticks([]), plt.yticks([])

    plt.subplot(153), plt.imshow(new_image2, cmap="gray")
    plt.title("Preprocessed Mode 2")
    plt.xticks([]), plt.yticks([])

    plt.subplot(154), plt.imshow(new_image3, cmap="gray")
    plt.title("Best of both worlds")
    plt.xticks([]), plt.yticks([])

    plt.subplot(155), plt.imshow(new_image4, cmap="gray")
    plt.title("Preprocessed Mode 3")
    plt.xticks([]), plt.yticks([])

    plt.tight_layout()
    plt.show()
