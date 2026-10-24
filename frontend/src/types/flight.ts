export interface FlightQuery {
  carrier: string;
  flight_number: string;
  departure_date: string;
}

export interface AircraftInfo {
  icao_type: string;
  tail_number: string;
  category: 'REGIONAL' | 'NARROWBODY' | 'WIDEBODY';
}

export interface FlightLeg {
  flight_number: string;
  origin_iata: string;
  destination_iata: string;
  scheduled_departure: string;
  scheduled_arrival: string;
  actual_departure?: string | null;
  actual_arrival?: string | null;
  status: string;
}

export interface InboundTurnaround {
  previous_legs: FlightLeg[];
  assigned_aircraft: AircraftInfo;
  mtt_minutes: 35 | 45 | 75;
  estimated_touchdown: string;
  earliest_possible_departure: string;
}

export interface SwapHeuristic {
  origin_is_hub: boolean;
  hub_type: 'FORTRESS_HUB' | 'OUTSTATION';
  swap_probability: 'HIGH' | 'MODERATE' | 'LOW' | 'NEAR_ZERO';
}

export interface AirspaceAdvisory {
  airport_iata: string;
  program_type: 'GROUND_STOP' | 'GROUND_DELAY_PROGRAM' | 'DEICING' | 'NORMAL';
  reason?: string | null;
  avg_delay_minutes: number;
  advisory_active: boolean;
}

export interface AlternativeFlight {
  flight_number: string;
  carrier: string;
  departure_time: string;
  arrival_time: string;
  origin_iata: string;
  destination_iata: string;
  seats_available: boolean;
  standby_recommended: boolean;
}

export interface RealityAssessment {
  flight_query: FlightQuery;
  official_airline_departure: string;
  calculated_earliest_departure: string;
  delay_lead_time_minutes: number;
  is_unavoidable_delay: boolean;
  swap_evaluation: SwapHeuristic;
  rebooking_directive: 'RELAX_IN_LOUNGE' | 'MONITOR_CLOSELY' | 'EXPEDITE_REBOOKING';
  airspace_advisory?: AirspaceAdvisory | null;
  alternative_flights?: AlternativeFlight[];
}

export interface LiveTelemetry {
  callsign?: string;
  baro_altitude_ft?: number | null;
  ground_speed_kts?: number | null;
  on_ground?: boolean;
  latitude?: number;
  longitude?: number;
  last_contact_epoch?: number;
}
