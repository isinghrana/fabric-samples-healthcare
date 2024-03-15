SELECT  a.[safetyreportid]
        ,lower(a.[reactionmeddrapt]) AS [reactionmeddrapt] 
        ,CAST(b.[receivedate] as date) AS [receivedate]
FROM [YOURLAKEHOUSENAME].[dbo].[fda_drug_event_patient_reaction] a
LEFT JOIN [YOURLAKEHOUSENAME].[dbo].[fda_drug_event] b ON a.[safetyreportid] = b.[safetyreportid]
WHERE [reactionmeddrapt] = 'FATIGUE' OR [reactionmeddrapt] = 'Fatigue' OR [reactionmeddrapt] = 'INSOMNIA' OR [reactionmeddrapt] = 'Insomnia'
