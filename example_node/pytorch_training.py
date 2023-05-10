import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
from torchvision.datasets import CIFAR10

DEVICE = torch.device("cpu")
print(f"Training on {DEVICE} using PyTorch {torch.__version__}")

BATCH_SIZE = 32


def load_datasets():
    """Download and transform CIFAR-10 (train and test)."""
    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
    )
    trainset = CIFAR10(
        "./dataset", train=True, download=True, transform=transform
    )
    testset = CIFAR10(
        "./dataset", train=False, download=True, transform=transform
    )
    return DataLoader(
        trainset, batch_size=BATCH_SIZE, shuffle=True
    ), DataLoader(testset, batch_size=BATCH_SIZE)


class Net(nn.Module):
    """Neural network model."""

    def __init__(self) -> None:
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(3, 6, 5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.fc1 = nn.Linear(16 * 5 * 5, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, 10)

    """Forward pass of the network."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(-1, 16 * 5 * 5)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x


def train(net, trainloader, epochs: int, verbose=False):
    """Train the network on the training set."""
    criterion = torch.nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(net.parameters())
    net.train()
    for epoch in range(epochs):
        correct, total, epoch_loss = 0, 0, 0.0
        for images, labels in trainloader:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            optimizer.zero_grad()
            outputs = net(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            # Metrics
            epoch_loss += loss
            total += labels.size(0)
            correct += (torch.max(outputs.data, 1)[1] == labels).sum().item()
        epoch_loss /= len(trainloader.dataset)
        epoch_acc = correct / total
        if verbose:
            print(
                f"Epoch {epoch+1}: train loss {epoch_loss},"
                + f"accuracy {epoch_acc}"
            )


def test(net, testloader):
    """Evaluate the network on the entire test set."""
    criterion = torch.nn.CrossEntropyLoss()
    correct, total, loss = 0, 0, 0.0
    net.eval()
    with torch.no_grad():
        for images, labels in testloader:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            outputs = net(images)
            loss += criterion(outputs, labels).item()
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
    loss /= len(testloader.dataset)
    accuracy = correct / total
    return loss, accuracy


trainloader, testloader = load_datasets()

model = torchvision.models.resnet18(weights="DEFAULT")
model.fc = torch.nn.Linear(
    model.fc.in_features, len(np.unique(testloader.dataset.targets))
)
net = Net().to(DEVICE)

for epoch in range(100):
    train(net, trainloader, 1)
    loss, accuracy = test(net, testloader)
    # print(f"\nEpoch {epoch+1}: validation loss {loss:.5f},"
    #    + f"accuracy {accuracy}")
