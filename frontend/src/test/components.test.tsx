import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FlightSearch } from '../components/FlightSearch';
import { GroundRealityCard } from '../components/GroundRealityCard';
import { RealityAssessment } from '../types/flight';

describe('FlightSearch Component', () => {
  it('validates carrier code and rejects invalid input', () => {
    const onSearchMock = vi.fn();
    render(<FlightSearch onSearch={onSearchMock} isLoading={false} />);

    const carrierInput = screen.getByLabelText(/carrier/i);
    const submitBtn = screen.getByRole('button', { name: /scan turnaround/i });

    // Enter lowercase / invalid carrier
    fireEvent.change(carrierInput, { target: { value: '1' } });
    fireEvent.click(submitBtn);

    expect(onSearchMock).not.toHaveBeenCalled();
    expect(
      screen.getByText(/carrier must be exactly 2 uppercase letters/i)
    ).toBeInTheDocument();
  });

  it('triggers onSearch when input is valid', () => {
    const onSearchMock = vi.fn();
    render(<FlightSearch onSearch={onSearchMock} isLoading={false} />);

    const carrierInput = screen.getByLabelText(/carrier/i);
    const flightInput = screen.getByLabelText(/flight #/i);
    const submitBtn = screen.getByRole('button', { name: /scan turnaround/i });

    fireEvent.change(carrierInput, { target: { value: 'DL' } });
    fireEvent.change(flightInput, { target: { value: '888' } });
    fireEvent.click(submitBtn);

    expect(onSearchMock).toHaveBeenCalledWith('DL', '888', expect.any(String));
  });
});

describe('GroundRealityCard Component', () => {
  const mockAssessmentDelay: RealityAssessment = {
    flight_query: {
      carrier: 'UA',
      flight_number: '1422',
      departure_date: '2026-10-24',
    },
    official_airline_departure: '2026-10-24T18:30:00Z',
    calculated_earliest_departure: '2026-10-24T19:15:00Z',
    delay_lead_time_minutes: 45,
    is_unavoidable_delay: true,
    swap_evaluation: {
      origin_is_hub: false,
      hub_type: 'OUTSTATION',
      swap_probability: 'NEAR_ZERO',
    },
    rebooking_directive: 'EXPEDITE_REBOOKING',
  };

  it('renders unavoidable delay, lead time delta, and rebooking directive', () => {
    render(<GroundRealityCard assessment={mockAssessmentDelay} />);

    // Assert Flight Title
    expect(screen.getByText('UA 1422')).toBeInTheDocument();

    // Assert Early Warning Lead Time Delta badge (+45 min ahead)
    expect(screen.getByText(/\+45 min ahead/i)).toBeInTheDocument();

    // Assert Turn Physics Badge
    expect(screen.getByText(/unavoidable delay/i)).toBeInTheDocument();

    // Assert Spare Swap Badge (Near 0% Outstation)
    expect(screen.getByText(/near 0% \(outstation\)/i)).toBeInTheDocument();

    // Assert Prescriptive Action Banner
    expect(
      screen.getByText(/immediate action: expedite rebooking/i)
    ).toBeInTheDocument();
  });

  it('renders relaxed state when flight is on time', () => {
    const mockAssessmentOnTime: RealityAssessment = {
      flight_query: {
        carrier: 'DL',
        flight_number: '450',
        departure_date: '2026-10-24',
      },
      official_airline_departure: '2026-10-24T12:00:00Z',
      calculated_earliest_departure: '2026-10-24T11:45:00Z',
      delay_lead_time_minutes: 0,
      is_unavoidable_delay: false,
      swap_evaluation: {
        origin_is_hub: true,
        hub_type: 'FORTRESS_HUB',
        swap_probability: 'LOW',
      },
      rebooking_directive: 'RELAX_IN_LOUNGE',
    };

    render(<GroundRealityCard assessment={mockAssessmentOnTime} />);

    expect(screen.getByText('DL 450')).toBeInTheDocument();
    expect(screen.getByText(/on schedule/i)).toBeInTheDocument();
    expect(screen.getByText(/feasible turn/i)).toBeInTheDocument();
    expect(screen.getByText(/relax in lounge/i)).toBeInTheDocument();
  });

  it('renders active FAA Ground Stop advisory alert banner', () => {
    const mockAssessmentWithGroundStop: RealityAssessment = {
      ...mockAssessmentDelay,
      airspace_advisory: {
        airport_iata: 'ORD',
        program_type: 'GROUND_STOP',
        reason: 'THUNDERSTORMS',
        avg_delay_minutes: 75,
        advisory_active: true,
      },
    };

    render(<GroundRealityCard assessment={mockAssessmentWithGroundStop} />);

    expect(screen.getByTestId('airspace-advisory-banner')).toBeInTheDocument();
    expect(
      screen.getByText(/FAA Airspace Alert: GROUND STOP Active at ORD/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/THUNDERSTORMS/i)).toBeInTheDocument();
    expect(screen.getByText(/75 min/i)).toBeInTheDocument();
  });

  it('renders alternative flights section with seats available and standby badges', () => {
    const mockAssessmentWithAlternatives: RealityAssessment = {
      ...mockAssessmentDelay,
      alternative_flights: [
        {
          flight_number: 'UA1588',
          carrier: 'UA',
          departure_time: '2026-10-24T19:30:00Z',
          arrival_time: '2026-10-24T22:00:00Z',
          origin_iata: 'ORD',
          destination_iata: 'EWR',
          seats_available: true,
          standby_recommended: false,
        },
        {
          flight_number: 'UA2104',
          carrier: 'UA',
          departure_time: '2026-10-24T20:45:00Z',
          arrival_time: '2026-10-24T23:15:00Z',
          origin_iata: 'ORD',
          destination_iata: 'EWR',
          seats_available: false,
          standby_recommended: true,
        },
      ],
    };

    render(<GroundRealityCard assessment={mockAssessmentWithAlternatives} />);

    expect(screen.getByTestId('alternative-flights-section')).toBeInTheDocument();
    expect(screen.getByText('UA1588')).toBeInTheDocument();
    expect(screen.getByText(/seats available/i)).toBeInTheDocument();
    expect(screen.getByText('UA2104')).toBeInTheDocument();
    expect(screen.getByText(/standby recommended/i)).toBeInTheDocument();
  });

  it('renders crew duty limit watchdog banner when timeout risk is HIGH', () => {
    const mockAssessmentWithCrewTimeout: RealityAssessment = {
      ...mockAssessmentDelay,
      crew_duty: {
        elapsed_duty_minutes: 810,
        remaining_buffer_minutes: 30,
        timeout_risk: 'HIGH',
        risk_summary: 'Critical timeout risk: remaining duty buffer (30m) is under 60 minutes.',
      },
    };

    render(<GroundRealityCard assessment={mockAssessmentWithCrewTimeout} />);

    expect(screen.getByTestId('crew-duty-banner')).toBeInTheDocument();
    expect(
      screen.getByText(/FAA Part 117 Watchdog: Crew Timeout Warning/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Buffer: 30m/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Inbound delay puts flight crew within/i)
    ).toBeInTheDocument();
  });
});
