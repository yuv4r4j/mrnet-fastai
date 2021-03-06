import numpy as np
import matplotlib.pyplot as plt
from scipy import ndimage as nd
from fastai.vision import *


# ItemBase subclass
class MRNetCase(ItemBase):

  # ItemBase.data   # this needs to be developed in parallel with the ItemList's .get method
  # imagine that .get will return a list of three np.arrays, an array for each plane
    def __init__(self, axial, coronal, sagittal):
        self.axial,self.coronal,self.sagittal = axial,coronal,sagittal
        self.obj = (axial,coronal,sagittal)
        self.data = np.stack([axial,coronal,sagittal], axis=0)
        
  # __str__ representation, or __repr__, since __str__ falls back on __repr__ if not otherwise defined
    def __repr__(self): 
        return f'''
        {self.__class__.__name__} 
        `obj` attribute is tuple(axial, coronal, sagittal): 
        {list(e.shape for e in self.obj)}
            
        `data` attribute is all three planar scan data arrays, 
        with variations in slice count removed via interpolation
        {self.data.shape}
        {self.data}
        '''

  # apply_tfms (optional)

# DataBunch subclass
class MRNetCaseDataBunch(DataBunch):
    "DataBunch for MRNet knee scan data."
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_df(cls, path:PathOrStr, df:pd.DataFrame, folder:PathOrStr=None, label_delim:str=None, valid_pct:float=0.2,
                fn_col:IntsOrStrs=0, label_col:IntsOrStrs=1, suffix:str='', **kwargs:Any)->'ImageDataBunch':
        "Create DataBunch from a `DataFrame` `df`."
        src = (MRNetCaseList.from_df(df, path=path, folder=folder, suffix=suffix, cols=fn_col)
                .split_by_rand_pct(valid_pct)
                .label_from_df(label_delim=label_delim, cols=label_col))
        return cls.create_from_ll(src, **kwargs)


# ItemList subclass
class MRNetCaseList(ItemList):
  # class variables
    _bunch = MRNetCaseDataBunch
    # _processor
    # _label_cls

  # __init__ arguments
  # items for this subclass will likely be a list/iterator of Case strings
  # rather than filenames, since each case has 3 filenames, one for each plane
#   "Any additional arguments to the __init__ call that are saved in the ItemList's state must be passed
#   along in the `new` method, because that is what is used to created train and validation sets when splitting.
#   To do that, need to add their names in the `copy_new` argument of custom ItemList during the __init__.
#   However, be sure to keep **kwargs as is."
    def __init__(self, items, path, **kwargs):
        super().__init__(items=items, path=path, **kwargs)

  # core methods
    # get
    def get(self, i):
        # i indexes self.items, which is an ordered array of case numbers as strings
        case = super().get(i)
#       cases belong to either train or valid split in the folder structure
        tv = 'train' if (self.path/'train'/'axial'/(case + '.npy')).exists() else 'valid'
        imagearrays = []
        for plane in ('axial','coronal','sagittal'):
            # self.path is available from kwargs of ItemList superclass
            fn  = self.path/tv/plane/(case + '.npy')
            res = self.open(fn)
            imagearrays.append(res) 
        assert len(imagearrays) == 3
        return MRNetCase(*imagearrays)

    # since subclassing ItemList rather than ImageList, need an open method
    def open(self, fn): return np.load(fn)

    def reconstruct(self, t):
        # t is the pytorch tensor corresponding to the .data attribute of MRNetCase
        # the result of reconstruct should be to 
        # "return the same kind of object as .get returns"
        # which is a MRNetCase 
        # and to build that, a tuple of numpy arrays is required
        arrays = to_np(t)
        return MRNetCase(arrays[0,:,:,:],arrays[1,:,:,:],arrays[2,:,:,:]) 

    def show_batch(self, rows:int=4, ds_type:DatasetType=DatasetType.Train, **kwargs)->None:
        "Show a batch of data in `ds_type` on a few `rows`."
        x,y = self.one_batch(ds_type, True, True)
        n_items = rows
        if self.dl(ds_type).batch_size < n_items: n_items = self.dl(ds_type).batch_size
        xs = [self.train_ds.x.reconstruct(grab_idx(x, i)) for i in range(n_items)]
        #TODO: get rid of has_arg if possible
        if has_arg(self.train_ds.y.reconstruct, 'x'):
            ys = [self.train_ds.y.reconstruct(grab_idx(y, i), x=x) for i,x in enumerate(xs)]
        else : ys = [self.train_ds.y.reconstruct(grab_idx(y, i)) for i in range(n_items)]
        self.train_ds.x.show_xys(xs, ys, **kwargs)

    # custom show_xys method for show_batch
    # would like to have each row correspond to a case from three planes
    def show_xys(self, xs, ys, imgsize:int=4, 
                 figsize:Tuple[int,int]=(13,13), **kwargs):
        "Show the `xs` (inputs) and `ys` (targets) on a figure of `figsize`."
        rows = len(xs)
        fig, axarray = plt.subplots(rows, 3, figsize=figsize)        
        # start by showing the middle slice, from each plane
        planes = ('axial','coronal','sagittal')
        for i,(x,y) in enumerate(zip(xs, ys)):
            for p,plane in enumerate(planes): 
                axarray[i,p].imshow(x.data[p,11,:,:])
                axarray[i,p].set_title('{} ({})'.format(y, plane))
        plt.tight_layout()
    # TODO: def show_xyzs # once have predictions to work with

    # TODO: def analyze_pred                                                                                                                                                                                                                                                                                                                    

    @classmethod
    def from_folder(cls, path:PathOrStr='.', extensions:Collection[str]=['.npy'], **kwargs)->'MRNetCaseList':
        "Get the Case numbers for all MRNet cases, assuming directory structure unchanged from MRNet data download"
        filepaths = get_files(path=path, extensions=extensions, recurse=True, **kwargs)
        items = sorted(set([fp.stem for fp in filepaths]))
        return cls(items=items, path=path)

    def split_by_folder(self, train:str='train', valid:str='valid') -> 'MRNetCaseLists':
        # given the list of items in the itemlist
        # construct lists of train and valid indexes
        # check whether the item is in a train folder or a validation folder
        # arbitrarily choosing axial subfolder to check for case array
        valid_idx = [i for i,case in enumerate(self.items) if (self.path/'valid'/'axial'/(case + '.npy')).exists()]
        # then use split_by_idx to return split item lists
        return self.split_by_idx(valid_idx=valid_idx)

    def link_label_df(self, df):
        "Associate labels to cases using pandas DataFrame having Case column and one or more label columns"
        # want to be able to use the existing fastai code around multiple labels and such
        # so, need to associate a df to the CaseList object
        # which will be referenced in multiple places as self.inner_df
        # first join the df to the case numbers in self.items
        casesDF = pd.DataFrame({'Case': self.items})
        self.inner_df = pd.merge(casesDF, df, on ='Case')


