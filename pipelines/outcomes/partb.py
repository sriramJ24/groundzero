import pandas as pd, numpy as np, json, datetime, warnings
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.inspection import permutation_importance
warnings.filterwarnings('ignore')
D='cache/ipk/'
def load(rep,meta,trt):
    d=pd.read_csv(D+rep,sep=';',low_memory=False,encoding='latin1',decimal=',')
    d=d[d['Row Type']=='combined'].copy()
    m=pd.read_csv(D+meta,sep=';',encoding='latin1').drop_duplicates('Carrier_ID')[['Carrier_ID','Genotypes']]
    d=d.merge(m,left_on='Plant ID',right_on='Carrier_ID',how='left'); d['trt']=trt
    return d
dc=load('control_report.csv','Metadata_Control.csv',0); ds=load('stress_report.csv','Metadata_Stress.csv',1)
print(dc.shape,ds.shape)
TR={'bv':'volume iap (zoom-corrected geometry trait based on visible-light combined view) [voxel]',
'area':'area (zoom-corrected geometry trait based on visible-light side view) [mm^2]',
'height':'height (zoom-corrected geometry trait based on visible-light side view) [mm]',
'g_mean':'rgb green mean (color-related trait based on visible-light top view)',
'r_mean':'rgb red mean (color-related trait based on visible-light top view)',
'b_mean':'rgb blue mean (color-related trait based on visible-light top view)',
'lab_a':'lab a mean (color-related trait based on visible-light top view)'}
for k,v in TR.items(): assert v in dc.columns and v in ds.columns,k
A=pd.concat([dc,ds],ignore_index=True)
A['day']=A['Day [Int]'].astype(int)
for k,v in TR.items(): A[k]=pd.to_numeric(A[v],errors='coerce')
A['pid']=A['trt'].astype(str)+'_'+A['Plant ID'].astype(str)
A=A.dropna(subset=['Genotypes'])
print(A.groupby('trt').day.agg(['min','max']), A.groupby('trt')['pid'].nunique(), A.Genotypes.nunique())
# growth curves
gc=A.groupby(['trt','day']).bv.mean().unstack(0).dropna()
print(gc.to_string())
json.dump({'tmp':1},open('/dev/null','w'))
A.to_pickle('cache/A.pkl')
