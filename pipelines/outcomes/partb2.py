import pandas as pd, numpy as np, json, datetime, warnings
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.inspection import permutation_importance
warnings.filterwarnings('ignore')
A=pd.read_pickle('cache/A.pkl')
TR=['bv','area','height','g_mean','r_mean','b_mean','lab_a']
PRE_MAX,EARLY_MAX,T_STRESS_END,T_REC_END=7,10,21,35
def last(g,lo,hi,c):
    x=g[(g.day>=lo)&(g.day<=hi)].dropna(subset=[c]).sort_values('day')
    return (x[c].iloc[-1],x.day.iloc[-1]) if len(x) else (np.nan,np.nan)
rows=[]
for pid,g in A.groupby('pid'):
    r={'pid':pid,'geno':g.Genotypes.iloc[0],'trt':int(g.trt.iloc[0])}
    for c in TR:
        v,dp=last(g,0,PRE_MAX,c); e,de=last(g,PRE_MAX+1,EARLY_MAX,c)
        r[c+'_pre']=v; r[c+'_early']=e
        if c=='bv': r['bv_dpre'],r['bv_dearly']=dp,de
    r['bv_lograte']=np.log(r['bv_early']/r['bv_pre'])/(r['bv_dearly']-r['bv_dpre']) if r['bv_pre']>0 and r['bv_early']>0 else np.nan
    for c in ['area','height']:
        r[c+'_lograte']=np.log(r[c+'_early']/r[c+'_pre'])/(r['bv_dearly']-r['bv_dpre']) if r[c+'_pre']>0 and r[c+'_early']>0 else np.nan
    r['bv_stress_end']=g.loc[g.day==T_STRESS_END,'bv'].mean(); r['bv_rec_end']=g.loc[g.day==T_REC_END,'bv'].mean()
    rows.append(r)
P=pd.DataFrame(rows)
P=P.dropna(subset=['bv_pre','bv_early','bv_stress_end','bv_rec_end']).reset_index(drop=True)
# genotype control mean at target day (target definition only)
ctl=P[P.trt==0].groupby('geno')[['bv_stress_end','bv_rec_end']].mean().add_suffix('_gctl')
P=P.merge(ctl,left_on='geno',right_index=True,how='left')
P['loss_stress_end']=1-P.bv_stress_end/P.bv_stress_end_gctl
P['loss_rec_end']=1-P.bv_rec_end/P.bv_rec_end_gctl
# carried-forward relative baseline: day-10 BV relative to genotype control mean day-10
c10=A[(A.trt==0)&(A.day==EARLY_MAX)].groupby('Genotypes').bv.mean().rename('bv10_gctl')
P=P.merge(c10,left_on='geno',right_index=True,how='left')
P['loss_cf']=1-P.bv_early/P.bv10_gctl
FEATS=['trt']+[c+s for c in TR for s in ('_pre','_early')]+['bv_lograte','area_lograte','height_lograte']
print(len(P),P.geno.nunique(),P.trt.value_counts().to_dict())
def cv(df,feats,target,baselines,seed=0):
    df=df.dropna(subset=[target]).reset_index(drop=True)
    gkf=GroupKFold(n_splits=5)
    oof=np.zeros(len(df)); base={k:np.zeros(len(df)) for k in baselines}; imps=[]
    for tr,te in gkf.split(df,groups=df.geno):
        m=HistGradientBoostingRegressor(random_state=seed).fit(df.loc[tr,feats],df.loc[tr,target])
        oof[te]=m.predict(df.loc[te,feats])
        pi=permutation_importance(m,df.loc[te,feats],df.loc[te,target],n_repeats=3,random_state=0,scoring='neg_mean_absolute_error')
        imps.append(pd.Series(pi.importances_mean,index=feats))
        for k,f in baselines.items(): base[k][te]=f(df,tr,te,target)
    y=df[target].values
    mean=abs(y.mean())
    met=lambda p:{'r2':float(r2_score(y,p)),'mae':float(mean_absolute_error(y,p)),'mae_pct':float(100*mean_absolute_error(y,p)/mean)}
    return df,{'model':met(oof),'baselines':[{'name':k,**{a:b for a,b in met(v).items() if a!='mae_pct'},'mae_pct':met(v)['mae_pct']} for k,v in base.items()],'n_plants':int(len(df)),'n_genotypes':int(df.geno.nunique()),'target_mean':float(y.mean())},pd.concat(imps,axis=1).mean(axis=1)
def grp_mean(df,tr,te,t): 
    m=df.loc[tr].groupby('trt')[t].mean(); return df.loc[te,'trt'].map(m).values
def cf_abs(col):
    return lambda df,tr,te,t: df.loc[te,col].values
def cf_loss(df,tr,te,t): return df.loc[te,'loss_cf'].fillna(df.loc[tr,t].mean()).values
out=[];imp_all={}
for name,t in [('biovolume_end_of_stress_day21','bv_stress_end'),('biovolume_end_of_recovery_day35','bv_rec_end')]:
    _,r,imp=cv(P,FEATS,t,{'treatment_group_mean':grp_mean,'last_observed_carried_forward_day10':cf_abs('bv_early')})
    out.append({'name':name,**r}); imp_all[name]=imp
S=P[P.trt==1].copy(); FS=[f for f in FEATS if f!='trt']
for name,t in [('relative_growth_loss_vs_genotype_control_end_of_stress_day21','loss_stress_end'),('relative_growth_loss_vs_genotype_control_end_of_recovery_day35','loss_rec_end')]:
    S2=S.dropna(subset=[t])
    _,r,imp=cv(S2,FS,t,{'stress_group_mean':lambda df,tr,te,tt:np.full(len(te),df.loc[tr,tt].mean()),'last_observed_loss_carried_forward_day10':cf_loss})
    out.append({'name':name,**r,'note':'stress plants only; loss = 1 - BV/mean BV of same genotype in the control experiment at the same day'}); imp_all[name]=imp
top=pd.concat(imp_all,axis=1).mean(axis=1).sort_values(ascending=False).head(10)
top_features=[{'feature':k,'permutation_importance_mae_increase_mean_over_targets':float(v)} for k,v in top.items()]
# effects
gc=A.groupby(['trt','day']).bv.mean().unstack(0).dropna()
cm,sm=gc[0],gc[1]
ex=lambda d:{'control_mean':float(cm[d]),'stress_mean':float(sm[d]),'pct_reduction':float(100*(1-sm[d]/cm[d]))}
te={'day':T_STRESS_END,**ex(T_STRESS_END),'at_day_recovery_end':{'day':T_REC_END,**ex(T_REC_END)},
 'at_pre_stress_day6':{'day':6,**ex(6)},
 'confound_note':'Control and stress are separate experiments (different dates); stress plants were already smaller before stress began, so the raw difference overstates the stress effect.',
 'ratio_stress_over_control_day6':float(sm[6]/cm[6]),'ratio_stress_over_control_day21':float(sm[21]/cm[21]),
 'ratio_adjusted_pct_reduction_day21':float(100*(1-(sm[21]/cm[21])/(sm[6]/cm[6])))}
print(json.dumps(te,indent=1))
res={'dataset':{'name':'High-throughput shoot phenotyping of maize under combined drought and heat stress (IPK e!DAL, files 2228AL_Stress_report.csv + 2237RS_Control_report.csv + Metadata_*.csv)','doi':'10.5447/ipk/2025/8','license':'CC BY 4.0','citation':'Shi, R. (2025): High-throughput shoot phenotyping of maize under combined drought and heat stress. e!DAL - Plant Genomics & Phenomics Research Data Repository, IPK Gatersleben. https://doi.org/10.5447/ipk/2025/8','n_plants':int(len(P)),'n_genotypes':int(P.geno.nunique())},
'design':{'experiments':'control (2237RS, 25/20C, 70% FC) vs combined drought+heat (2228AL, 35/25C, 30% FC); separate runs','day_axis':'IAP Day [Int] (days in the imaging system); assumed stress days 8-21 and recovery days 22-35 per dataset description (stress one week after transplant, 2 weeks, then 2 weeks recovery)',
 'features':FEATS,'feature_windows':'pre-stress = last image on days <=7; early stress = last image on days 8-10 (days 8 and 10 are imaged); treatment flag',
 'biovolume':'volume iap, zoom-corrected, visible-light combined view [voxel]','targets':'BV at day 21 (end of stress), BV at day 35 (end of recovery), and relative loss vs same-genotype control mean',
 'cv':'GroupKFold(5), group=genotype, default HistGradientBoostingRegressor(random_state=0), no tuning; metrics on pooled out-of-fold predictions','baselines':'treatment-group mean (train folds); day-10 value carried forward'},
'targets':out,'top_features':top_features,'treatment_effect':te,
'growth_curves':{'days':[int(d) for d in gc.index],'control_mean':[float(x) for x in cm],'stress_mean':[float(x) for x in sm],'unit':'biovolume, voxel (zoom-corrected)'},
'limitations':['Greenhouse pots with automated imaging platform, not a field; single hybrid-free inbred-line panel; not this farm and not a farm-calibrated model.','Control and stress were separate experiments; stress plants were already ~60% smaller at day 6, so treatment effects and relative loss vs control are confounded with experiment/run differences.','Day alignment (stress start day 8) is assumed from the dataset description, not read from a conditions file.','Input features come from imaging-platform traits (side/top views, fluorescence-derived), not from a farm camera; the model is for ranking relative stress response, not calibrated yield prediction.','Genotype count includes all genotypes present in the metadata (may include reference/blank entries beyond the 106 lines).','Held-out whole genotypes, but with n~380 plants per arm and default hyperparameters; reported metrics are single-run, untuned.'],
'status':'ok','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
json.dump(res,open('/Users/sriramjoshi/Code/Hackathons/GroundZero/groundzero/frontend/public/data/outcome_eval.json','w'),indent=2)
for t in out: print(t['name'],t['model'],[(b['name'],round(b['r2'],3),round(b['mae_pct'],1)) for b in t['baselines']],t['n_plants'],t['n_genotypes'])
print(top_features[:5])
