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
});
