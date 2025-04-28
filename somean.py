import pyseistr as ps
import numpy as np

def smooth(a,WSZ):
    # a: NumPy 1-D array containing the data to be smoothed
    # WSZ: smoothing window size needs, which must be odd number,
    # as in the original MATLAB implementation
    out0 = np.convolve(a,np.ones(WSZ,dtype=int),'valid')/WSZ    
    r = np.arange(1,WSZ-1,2)
    start = np.cumsum(a[:WSZ-1])[::2]/r
    stop = (np.cumsum(a[:-WSZ:-1])[::2]/r)[::-1]
    return np.concatenate((  start , out0, stop  ))

def somean(arr, radius, eps=0.1, order=3, rect=[20,20,1]):

    ## Slope estimation
    dtemp=arr*0
    for i in range(1,arr.shape[0]+1):
        dtemp[i-1,:]=smooth(arr[i-1,:],5)
   
    dip=ps.dip2dc(dtemp,rect=rect)
    ## Structural smoothing
    
    return ps.somean2dc(arr,dip,radius,order,eps)
    