import pandas as pd

def filter_large_csv_by_stay_ids(input_file, output_file, key_col, chunksize=100_000):
    valid_ids = [1000656, 1000657, 1000649, 1000650, 426]

    reader = pd.read_csv(input_file, chunksize=chunksize)
    first_chunk = True

    total_rows_kept = 0
    for i, chunk in enumerate(reader):
        filtered_chunk = chunk[chunk[key_col].isin(valid_ids)]
        total_rows_kept += len(filtered_chunk)

        if first_chunk:
            filtered_chunk.to_csv(output_file, index=False, mode='w')
            first_chunk = False
        else:
            filtered_chunk.to_csv(output_file, index=False, mode='a', header=False)

        print(f"Chunk {i+1} done. {len(filtered_chunk)} rows kept.")

def rename_converse(input_csv, output_csv):

    df = pd.read_csv(input_csv)

    mask = df['pharmaid'] == 426
    df.loc[mask, 'cumulativedose'] = df.loc[mask, 'cumulativedose'] * 1000

    df = df[["pharma_records/", "infusionid", "pharmaid", "givenat", "cumulativedose"]]
    df.rename(columns={'pharma_records/': 'subject_id'}, inplace=True)
    df.rename(columns={'pharmaid': 'item'}, inplace=True)
    df.rename(columns={'givenat': 'charttime'}, inplace=True)

    mapping = {1000656: 'norepinephrine', 1000657: 'norepinephrine', 1000649: 'epinephrine', 1000650: 'epinephrine', 426: 'dobutamine'}
    df["item"] = df["item"].map(mapping).fillna(df["item"])

    df.to_csv(output_csv, index=False)
    print(f"Done, result save to: {output_csv}")

def convert_infusion_csv(input_csv, output_csv):
    df = pd.read_csv(input_csv, parse_dates=['charttime'])

    df = df.sort_values(['infusionid', 'charttime'])

    grouped = df.groupby('infusionid')

    time_span = (
        grouped['charttime'].transform('max')
        - grouped['charttime'].transform('min')
    )

    df = df[time_span >= pd.Timedelta(hours=1)]

    grouped = df.groupby('infusionid')

    df['starttime'] = df['charttime']
    df['endtime'] = grouped['charttime'].shift(-1)

    df['dose'] = (
        grouped['cumulativedose'].shift(-1)
        - df['cumulativedose']
    )

    df = df.dropna(subset=['endtime', 'dose'])
    df = df[df['dose'] != 0]

    duration = (
            df['endtime'] - df['starttime']
        ).dt.total_seconds() / 60

    df = df[duration > 0]
    duration = duration[duration > 0]

    df['rate'] = df['dose'] / duration

    df = df.drop(columns=['charttime', 'cumulativedose'])

    df.to_csv(output_csv, index=False)

    return df

def add_weight(infusion_csv, weight_csv, output_csv):
    df = pd.read_csv(
        infusion_csv,
        parse_dates=['starttime', 'endtime']
    )
    weight = pd.read_csv(
        weight_csv,
        parse_dates=['charttime']
    )

    df['midtime'] = (
        df['starttime']
        + (df['endtime'] - df['starttime']) / 2
    )

    weight = weight[['subject_id', 'charttime', 'value']]
    weight = weight.rename(columns={'value': 'weight'})

    weight = weight.dropna(
        subset=['subject_id', 'charttime', 'weight']
    )

    df['subject_id'] = df['subject_id'].astype('int')
    weight['subject_id'] = weight['subject_id'].astype('int')

    df['_row_order'] = range(len(df))

    df = df.sort_values('midtime')
    weight = weight.sort_values('charttime')

    df = pd.merge_asof(
        df,
        weight,
        left_on='midtime',
        right_on='charttime',
        by='subject_id',
        direction='nearest'
    )

    df = df.sort_values('_row_order')

    df = df.drop(
        columns=['midtime', 'charttime', '_row_order']
    )

    mask = df['weight'].isna()
    df.loc[mask, 'weight'] = 77

    df['rate'] = df['rate'] / df['weight']

    df.to_csv(output_csv, index=False)

    return df

if __name__ == "__main__":

    filter_large_csv_by_stay_ids('../../hirid/pharma_records.csv', './adrenal.csv', 'pharmaid')
    rename_converse('./adrenal.csv', './adrenal.csv')
    convert_infusion_csv('./adrenal.csv', './adrenal.csv')
    add_weight('./adrenal.csv', './weight.csv', './adrenal.csv')