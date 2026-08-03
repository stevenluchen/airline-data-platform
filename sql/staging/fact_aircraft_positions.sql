select
    sv.icao24,
    sv.callsign,
    sv.origin_country,
    al.airline_name,
    al.iata as airline_iata,
    al.icao as airline_icao,
    ac.registration_number as aircraft_registration_number,
    ac.type as aircraft_type,
    ac.year as aircraft_registered_year

from raw.state_vectors sv
left join analytics.dim_airlines al
    on left(sv.callsign, 3) = al.icao
left join analytics.dim_aircraft ac
    on sv.icao24 = ac.icao24
-- where al.airline_name is null
--     and replace(ac.registration_number, '-', '') != sv.callsign

limit 100
;