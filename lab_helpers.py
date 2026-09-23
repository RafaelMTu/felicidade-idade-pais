
import pandas as pd
import country_converter as coco
import requests
import io

AGE_MID = {
    "up to 29 years": 22,
    "30-44 years": 37,
    "45-59 years": 52,
    "60+ years": 70,
}

WB_INDICATORS = {
    "NY.GDP.PCAP.PP.KD": "gdp_pc",      # GDP per capita
    "SP.POP.TOTL": "pop",              # Population, total
    "AG.LND.TOTL.K2": "area_km2",      # Land area
}

def to_iso3(country_names):
    """Converts country names to ISO3 codes using country_converter."""
    return coco.convert(names=country_names, to='iso3', not_found=None)

def build_country_table(wb_indicators=WB_INDICATORS, years=range(2019, 2024)):
    """Fetches World Bank indicators and returns a DataFrame with country data.
    The final table includes 'iso3', 'country_name' and the specified indicators."""
    all_countries_info = pd.DataFrame(columns=['iso3', 'country_name']) # To store unique iso3 and country_name mappings
    country_indicator_dfs = [] # To store indicator dataframes (iso3, value)

    for indicator_code, col_name in wb_indicators.items():
        url = f"http://api.worldbank.org/v2/country/all/indicator/{indicator_code}?format=json&date={min(years)}:{max(years)}&per_page=1000"
        response = requests.get(url).json()
        if response and len(response) > 1:
            data = response[1]
            indicator_df = pd.DataFrame(data)
            indicator_df = indicator_df.dropna(subset=['value'])
            if not indicator_df.empty:
                # Converter ID de 2 letras do Banco Mundial para 3 letras (ISO3)
                raw_ids = indicator_df['country'].apply(lambda x: x['id'])
                indicator_df['iso3'] = coco.convert(names=list(raw_ids), to='iso3', not_found=None)
                indicator_df['country_name'] = indicator_df['country'].apply(lambda x: x['value'])

                # Update the all_countries_info with new iso3-country_name pairs
                new_countries = indicator_df[['iso3', 'country_name']].dropna(subset=['iso3']).drop_duplicates(subset=['iso3'])
                all_countries_info = pd.concat([all_countries_info, new_countries], ignore_index=True).drop_duplicates(subset=['iso3'])

                # Prepare indicator data for merging later
                indicator_df = indicator_df.sort_values(by='date', ascending=False).drop_duplicates(subset=['iso3'])
                country_indicator_dfs.append(indicator_df[['iso3', 'value']].rename(columns={'value': col_name}))

    if all_countries_info.empty: # If no country data was found for any indicator
        return pd.DataFrame()

    # Start with all_countries_info as the base containing iso3 and country_name
    final_country_df = all_countries_info.copy()

    # Merge each indicator dataframe onto the base country list
    for df_ind in country_indicator_dfs:
        final_country_df = pd.merge(final_country_df, df_ind, on='iso3', how='left') # Use left join to keep all countries from all_countries_info

    # Remover códigos agregados conhecidos ou vazios
    final_country_df = final_country_df.dropna(subset=['iso3']) # Ensure no null iso3 after merges
    aggregate_codes = [
        "ARB", "CSS", "CEB", "EAS", "EAP", "TEA", "ECS", "EEC", "EUU", "FCS",
        "HIC", "HPC", "IBD", "IBT", "IDA", "IDB", "IDX", "LAC", "LCN", "LDC",
        "LMY", "LIC", "LMC", "MEA", "MNA", "MIC", "NAC", "OEC", "OED", "OSS",
        "PSS", "PST", "SAS", "SSA", "SSF", "SST", "SML", "UMC", "WLD"
    ]
    final_country_df = final_country_df[~final_country_df['iso3'].isin(aggregate_codes)].reset_index(drop=True)

    return final_country_df

def load_owid_age():
    """Loads OWID age data from CSV and transforms it to long format."""
    url = "https://ourworldindata.org/grapher/cantril-ladder-age-groups.csv?v=1&csvType=full&useColumnShortNames=true"
    data = requests.get(url).text
    raw_df = pd.read_csv(io.StringIO(data))

    owid_melted_df = raw_df.melt(
        id_vars=['entity', 'code', 'year'],
        var_name='age_group_raw',
        value_name='ladder_mean'
    )

    owid_melted_df['age_group'] = (
        owid_melted_df['age_group_raw']
        .str.replace('cantril_ladder_score__age_group_', '', regex=False)
        .str.replace('plus_years', '+ years', regex=False)
        .str.replace('_', ' ', regex=False)
        .str.strip()
    )
    owid_melted_df = owid_melted_df.drop(columns='age_group_raw')
    owid_melted_df = owid_melted_df.rename(columns={'entity': 'country', 'code': 'iso3'})
    owid_melted_df = owid_melted_df.dropna(subset=['iso3'])

    return owid_melted_df
