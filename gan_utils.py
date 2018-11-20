import torch
import torch.nn as nn
from torch.utils.data import Dataset
import numpy as np
from skimage import io, transform
from tqdm import tqdm

class flower_dataset(Dataset):
    
    def __init__(self, image_paths, mask_paths=None, mask_sizes=None, 
                 transform=None, mask_transform=None, in_memory=True):
        self.len = len(image_paths)
        self.transform = transform
        self.mask_transform = mask_transform
        self.in_memory = in_memory
        self.mask_sizes = mask_sizes
        
        if not self.in_memory:
            self.image_paths = image_paths
            if mask_paths is None:
                self.mask_paths = [None]*self.len
            else:
                self.mask_paths = mask_paths
            return
        
        self.image = []
        self.mask = []
        
        for i, path in tqdm(enumerate(image_paths)):
            image = io.imread(path)
            if (len(image.shape)!=3):
                self.len -= 1
                continue
                
            if self.transform is not None:
                image = self.transform(image)
            self.image.append(image)

            if mask_paths is None:
                self.mask.append(self.get_empty_masks())
            else:
                mask = io.imread(mask_paths[i], as_gray=True)
                masks = []
                for size in self.mask_sizes:
                    masks.append(self.get_mask(mask, size))
                self.mask.append(masks)

        
    def __len__(self):
        return self.len
    
    def __getitem__(self, idx):
        if self.in_memory:
            return self.image[idx], self.mask[idx]
        else:
            image_path = self.image_paths[idx]
            image = io.imread(image_path)
            if self.transform is not None:
                image = self.transform(image)
            
            mask_path = self.mask_paths[idx]
            if mask_path is None:
                masks = self.get_empty_masks()
            else:
                mask = io.imread(mask_path)
                masks = []
                for size in self.mask_sizes:
                    masks.append(self.get_mask(mask, size))
            return image, masks
            
    def get_empty_masks(self):
            return [-torch.ones(1,size,size,dtype=torch.float32) for size in self.mask_sizes]
        
    def get_mask(self, mask_, size=None):
        mask = mask_
        if (size is not None):
            mask = transform.resize(mask, (size, size)).astype('float32')
        if self.mask_transform is not None:
            mask = self.mask_transform(np.expand_dims(mask,axis=-1))
        return mask
    
def weights_init(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        nn.init.normal_(m.weight.data, 0.0, 0.02)
    elif classname.find('BatchNorm') != -1:
        nn.init.normal_(m.weight.data, 1.0, 0.02)
        nn.init.constant_(m.bias.data, 0)
        
def sample_mask(batch_size, sizes, realdata, noise_level=0.2, device=None):
    masks = [torch.randn(batch_size, 1, size, size, device=device, dtype=torch.float32) * noise_level for size in sizes]
    for i in range(batch_size):
        n = np.random.randint(len(realdata))
        for k, mask in enumerate(masks):
            mask[i,:,:,:] += realdata[n][1][k].to(device)
    return masks

def mask_pair_to_label(mask, real_mask, device=None):
    mask1 = mask[-1]
    mask2 = real_mask[-1]
    b_size = mask1.size()[0]
    mask_size = mask1.size()[-1]**2
    #label = ((mask1-mask2).abs()<0.4).view(b_size,-1).sum(1).float()/mask_size
    #label = label.to(device)
    label = torch.ones(b_size, device=device)
    label = label - ((mask1-mask2).abs()/2.0).view(b_size,-1).mean(1)
    return label

def get_label(size, real, soft=0.2, noise=False, noise_level=0.1, device=None):
    label = torch.full((size,), real, device=device)
    if real == 1:
        label -= torch.rand(size, device=device) * soft
    else:
        label += torch.rand(size, device=device) * soft
    if noise:
        perm = torch.randperm(label.size(0))
        idx = perm[:int(label.size(0)*noise_level)]
        label[idx] = 1 - label[idx]
    return label

def noise_input(data, noise_level=0, device=None, clip=False):
    if noise_level==0:
        return data.to(device)
    else:
        noise_data = torch.randn(data.size(), device=device) * noise_level
        noise_data += data.to(device)
        if clip:
            noise_data = torch.clamp(noise_data, -1, 1)
    return noise_data

def sigmoid(x, alpha=0.02):
    return 1/(1+np.exp(-alpha*x))