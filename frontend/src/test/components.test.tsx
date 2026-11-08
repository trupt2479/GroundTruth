import { render, screen, fireEvent, renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FlightSearch, formatLocalDate } from '../components/FlightSearch';
import { GroundRealityCard } from '../components/GroundRealityCard';
import { InboundVisualizer } from '../components/InboundVisualizer';
import { WatchlistDrawer } from '../components/WatchlistDrawer';
import { useFlightStream, MAX_RECONNECT_ATTEMPTS } from '../hooks/useFlightStream';
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

  it('populates fields when a quick scenario pill is clicked', () => {
    const onSearchMock = vi.fn();
    render(<FlightSearch onSearch={onSearchMock} isLoading={false} />);

    const carrierInput = screen.getByLabelText(/carrier/i) as HTMLInputElement;
    const flightInput = screen.getByLabelText(/flight #/i) as HTMLInputElement;

    // Click Scenario 2 (DL 450)
    const dlBtn = screen.getByTestId('scenario-btn-DL-450');
    fireEvent.click(dlBtn);

    expect(carrierInput.value).toBe('DL');
    expect(flightInput.value).toBe('450');

    // Click Scenario 3 (AA 1200)
    const aaBtn = screen.getByTestId('scenario-btn-AA-1200');
    fireEvent.click(aaBtn);

    expect(carrierInput.value).toBe('AA');
    expect(flightInput.value).toBe('1200');

    // Submit after scenario selection
    const submitBtn = screen.getByRole('button', { name: /scan turnaround/i });
    fireEvent.click(submitBtn);

    expect(onSearchMock).toHaveBeenCalledWith('AA', '1200', expect.any(String));
  });

  it('updates date to Today and Tomorrow when preset buttons are clicked', () => {
    const onSearchMock = vi.fn();
    render(<FlightSearch onSearch={onSearchMock} isLoading={false} />);

    const dateInput = screen.getByLabelText(/date/i) as HTMLInputElement;
    const todayBtn = screen.getByTestId('preset-today-btn');
    const tomorrowBtn = screen.getByTestId('preset-tomorrow-btn');

    const expectedToday = formatLocalDate(new Date());
    const tomorrowDate = new Date();
    tomorrowDate.setDate(tomorrowDate.getDate() + 1);
    const expectedTomorrow = formatLocalDate(tomorrowDate);

    // Click Tomorrow
    fireEvent.click(tomorrowBtn);
    expect(dateInput.value).toBe(expectedTomorrow);

    // Click Today
    fireEvent.click(todayBtn);
    expect(dateInput.value).toBe(expectedToday);
  });

  it('triggers showPicker on date input click if supported', () => {
    const onSearchMock = vi.fn();
    render(<FlightSearch onSearch={onSearchMock} isLoading={false} />);

    const dateInput = screen.getByLabelText(/date/i) as HTMLInputElement;
    const showPickerSpy = vi.fn();
    dateInput.showPicker = showPickerSpy;

    fireEvent.click(dateInput);
    expect(showPickerSpy).toHaveBeenCalled();
  });
});

describe('useFlightStream Hook Zero-Auto-Retry', () => {
  it('enforces MAX_RECONNECT_ATTEMPTS = 0 and does not initiate reconnection timeouts on error', () => {
    expect(MAX_RECONNECT_ATTEMPTS).toBe(0);

    let errorHandler: (() => void) | null = null;
    const closeSpy = vi.fn();

    class MockEventSource {
      close = closeSpy;
      addEventListener = vi.fn();
      set onerror(handler: () => void) {
        errorHandler = handler;
      }
      onopen = vi.fn();
    }

    vi.stubGlobal('EventSource', MockEventSource);

    const { result } = renderHook(() =>
      useFlightStream('UA', '1422', '2026-10-24')
    );

    // Simulate error event on connection
    act(() => {
      if (errorHandler) {
        errorHandler();
      }
    });

    expect(closeSpy).toHaveBeenCalled();
    expect(result.current.isConnected).toBe(false);
    expect(result.current.isReconnecting).toBe(false);
    expect(result.current.error).toContain('Live stream disconnected');

    vi.unstubAllGlobals();
  });
});

const mockAssessmentDelay: RealityAssessment = {
    flight_query: {
      carrier: 'UA',
      flight_number: '1422',
      departure_date: '2026-10-24',
    },
    origin_iata: 'ORD',
    destination_iata: 'EWR',
    origin_name: "Chicago O'Hare",
    destination_name: 'Newark Liberty',
    scheduled_departure: '2026-10-24T18:30:00Z',
    actual_or_estimated_departure: '2026-10-24T19:45:00Z',
    scheduled_arrival: '2026-10-24T21:00:00Z',
    actual_or_estimated_arrival: '2026-10-24T22:15:00Z',
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

describe('GroundRealityCard Component', () => {

  it('renders unavoidable delay, lead time delta, and rebooking directive', () => {
    render(<GroundRealityCard assessment={mockAssessmentDelay} />);

    // Assert Flight Title and Route
    expect(screen.getByText('UA 1422')).toBeInTheDocument();
    expect(screen.getAllByText(/ORD → EWR/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId('flight-milestones-subcard')).toBeInTheDocument();

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
      origin_iata: 'ATL',
      destination_iata: 'MCO',
      origin_name: 'Atlanta Hartsfield-Jackson',
      destination_name: 'Orlando International',
      scheduled_departure: '2026-10-24T12:00:00Z',
      actual_or_estimated_departure: '2026-10-24T12:00:00Z',
      scheduled_arrival: '2026-10-24T13:30:00Z',
      actual_or_estimated_arrival: '2026-10-24T13:30:00Z',
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

  it('opens notification modal and handles SMS alert submission', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'success',
        message: 'Successfully subscribed +15551234567 to alerts for UA1422 on 2026-10-24.',
        subscription: {
          flight_carrier: 'UA',
          flight_number: '1422',
          flight_date: '2026-10-24',
          recipient_type: 'SMS',
          destination: '+15551234567',
        },
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<GroundRealityCard assessment={mockAssessmentDelay} />);

    // Click "Get Real-Time Alerts"
    const alertBtn = screen.getByRole('button', { name: /get real-time alerts/i });
    fireEvent.click(alertBtn);

    // Modal should be visible
    expect(screen.getByText(/proactive alert dispatch/i)).toBeInTheDocument();

    // Try submit without destination -> client validation error
    const submitBtn = screen.getByRole('button', { name: /activate alerts/i });
    fireEvent.click(submitBtn);
    expect(screen.getByText(/please enter a destination address/i)).toBeInTheDocument();

    // Enter invalid phone
    const destInput = screen.getByLabelText(/mobile phone number/i);
    fireEvent.change(destInput, { target: { value: '123' } });
    fireEvent.click(submitBtn);
    expect(screen.getByText(/valid e\.164 phone number/i)).toBeInTheDocument();

    // Enter valid phone
    fireEvent.change(destInput, { target: { value: '+15551234567' } });
    fireEvent.click(submitBtn);

    expect(await screen.findByText(/successfully subscribed \+15551234567/i)).toBeInTheDocument();

    vi.unstubAllGlobals();
  });
});

describe('InboundVisualizer Component Live Transparency', () => {
  it('renders clean notice when previous_legs is empty', () => {
    const emptyTurnaround = {
      previous_legs: [],
      assigned_aircraft: {
        icao_type: 'B738',
        tail_number: 'N824DN',
        category: 'NARROWBODY' as const,
      },
      mtt_minutes: 45 as const,
      estimated_touchdown: '2026-11-04T18:00:00Z',
      earliest_possible_departure: '2026-11-04T18:45:00Z',
    };

    render(<InboundVisualizer turnaround={emptyTurnaround} liveTelemetry={null} />);

    expect(screen.getByTestId('no-rotations-notice')).toBeInTheDocument();
    expect(
      screen.getByText(/No upstream rotation legs reported by carrier dispatch. Operating on direct turnaround buffer./i)
    ).toBeInTheDocument();
    expect(screen.queryByText('UA210')).not.toBeInTheDocument();
    expect(screen.queryByText('UA584')).not.toBeInTheDocument();
  });

  it('renders inactive telemetry banner when aircraft is on ground or transponder dormant', () => {
    const turnaround = {
      previous_legs: [],
      assigned_aircraft: {
        icao_type: 'A321',
        tail_number: 'N450DL',
        category: 'NARROWBODY' as const,
      },
      mtt_minutes: 45 as const,
      estimated_touchdown: '2026-11-04T14:00:00Z',
      earliest_possible_departure: '2026-11-04T14:45:00Z',
    };

    const inactiveTelemetry = {
      callsign: 'DAL450',
      on_ground: true,
      baro_altitude_ft: null,
      ground_speed_kts: null,
    };

    render(<InboundVisualizer turnaround={turnaround} liveTelemetry={inactiveTelemetry} />);

    expect(screen.getByTestId('live-telemetry-inactive')).toBeInTheDocument();
    expect(screen.getByText(/Telemetry: On Ground \/ Inactive/i)).toBeInTheDocument();
    expect(screen.queryByText(/28,000 ft/i)).not.toBeInTheDocument();
  });

  it('renders active airborne stats when transponder is airborne with altitude', () => {
    const turnaround = {
      previous_legs: [],
      assigned_aircraft: {
        icao_type: 'B738',
        tail_number: 'N123UA',
        category: 'NARROWBODY' as const,
      },
      mtt_minutes: 45 as const,
      estimated_touchdown: '2026-11-04T18:00:00Z',
      earliest_possible_departure: '2026-11-04T18:45:00Z',
    };

    const activeTelemetry = {
      callsign: 'UAL1422',
      on_ground: false,
      baro_altitude_ft: 31000,
      ground_speed_kts: 460,
    };

    render(<InboundVisualizer turnaround={turnaround} liveTelemetry={activeTelemetry} />);

    expect(screen.getByTestId('live-telemetry-active')).toBeInTheDocument();
    expect(screen.getByText('Airborne')).toBeInTheDocument();
    expect(screen.getByText('31,000 ft')).toBeInTheDocument();
    expect(screen.getByText('460 kts')).toBeInTheDocument();
  });
});

describe('Watchlist Features (GT-WATCH-01)', () => {
  it('renders Watch Flight button in GroundRealityCard and triggers watchlist save', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 201,
      ok: true,
      json: async () => ({
        id: '123e4567-e89b-12d3-a456-426614174000',
        user_name: 'Trupti',
        carrier: 'UA',
        flight_number: '1422',
        departure_date: '2026-10-24',
        status: 'ARMED',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<GroundRealityCard assessment={mockAssessmentDelay} />);

    const watchBtn = screen.getByTestId('watch-flight-btn');
    expect(watchBtn).toBeInTheDocument();
    expect(screen.getByText(/watch flight/i)).toBeInTheDocument();

    fireEvent.click(watchBtn);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/watchlist',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_name: 'Trupti',
          carrier: 'UA',
          flight_number: '1422',
          departure_date: '2026-10-24',
        }),
      })
    );

    expect(await screen.findByText(/watching/i)).toBeInTheDocument();

    vi.unstubAllGlobals();
  });

  it('renders WatchlistDrawer and displays watched flights and delete action', async () => {
    const mockItems = [
      {
        id: 'item-dl-565',
        user_name: 'Trupti',
        carrier: 'DL',
        flight_number: '565',
        departure_date: '2026-11-05',
        origin_iata: 'DTW',
        destination_iata: 'SEA',
        origin_name: 'Detroit Metro',
        destination_name: 'Seattle Tacoma',
        scheduled_departure: '2026-11-05T01:11:00Z',
        t2_scheduled_fetch: '2026-11-04T23:11:00Z',
        status: 'ARMED',
        latest_assessment: {
          delay_lead_time_minutes: 0,
        },
        created_at: '2026-11-05T00:00:00Z',
      },
    ];

    const fetchMock = vi.fn().mockImplementation((_url: string, options?: RequestInit) => {
      if (options?.method === 'DELETE') {
        return Promise.resolve({ ok: true, json: async () => ({ status: 'success' }) });
      }
      return Promise.resolve({
        ok: true,
        json: async () => mockItems,
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const { rerender } = render(<WatchlistDrawer isOpen={false} onClose={vi.fn()} />);
    expect(screen.queryByTestId('watchlist-drawer')).not.toBeInTheDocument();

    rerender(<WatchlistDrawer isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByTestId('watchlist-drawer')).toBeInTheDocument();

    expect(await screen.findByText(/DL 565/i)).toBeInTheDocument();
    expect(screen.getByText(/DTW → SEA/i)).toBeInTheDocument();
    expect(screen.getByText(/Armed for T-2h check/i)).toBeInTheDocument();

    // Trigger delete
    const deleteBtn = screen.getByTestId('delete-watchlist-item-dl-565');
    await act(async () => {
      fireEvent.click(deleteBtn);
    });

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/watchlist/item-dl-565', { method: 'DELETE' });

    vi.unstubAllGlobals();
  });
  it('renders status badges for ARMED, EVALUATED_T2, DEPARTED and triggers Check Now manual milestone check', async () => {
    const mockItems = [
      {
        id: 'item-armed',
        user_name: 'Trupti',
        carrier: 'DL',
        flight_number: '100',
        departure_date: '2026-11-08',
        origin_iata: 'ATL',
        destination_iata: 'MCO',
        scheduled_departure: '2026-11-08T18:00:00Z',
        t2_scheduled_fetch: '2026-11-08T16:00:00Z',
        status: 'ARMED',
        created_at: '2026-11-08T00:00:00Z',
      },
      {
        id: 'item-evaluated',
        user_name: 'Trupti',
        carrier: 'UA',
        flight_number: '200',
        departure_date: '2026-11-08',
        origin_iata: 'ORD',
        destination_iata: 'EWR',
        scheduled_departure: '2026-11-08T14:00:00Z',
        t2_scheduled_fetch: '2026-11-08T12:00:00Z',
        status: 'EVALUATED_T2',
        latest_assessment: {
          delay_lead_time_minutes: 45,
          rebooking_directive: 'EXPEDITE_REBOOKING',
        },
        created_at: '2026-11-08T00:00:00Z',
      },
      {
        id: 'item-departed',
        user_name: 'Trupti',
        carrier: 'AA',
        flight_number: '300',
        departure_date: '2026-11-08',
        origin_iata: 'DFW',
        destination_iata: 'MIA',
        scheduled_departure: '2026-11-08T10:00:00Z',
        t2_scheduled_fetch: '2026-11-08T08:00:00Z',
        status: 'DEPARTED',
        created_at: '2026-11-08T00:00:00Z',
      },
    ];

    const fetchMock = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
      if (options?.method === 'POST' && url.includes('check-milestones')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ evaluated_count: 1, items_evaluated: ['DL 100'], alerts_dispatched: 0 }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => mockItems,
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<WatchlistDrawer isOpen={true} onClose={vi.fn()} />);

    expect(await screen.findByText(/DL 100/i)).toBeInTheDocument();
    expect(screen.getByTestId('status-badge-armed')).toBeInTheDocument();
    expect(screen.getByTestId('status-badge-evaluated')).toBeInTheDocument();
    expect(screen.getByTestId('status-badge-departed')).toBeInTheDocument();
    expect(screen.getByText(/Departed/i)).toBeInTheDocument();
    expect(screen.getByText(/T-2h Checked/i)).toBeInTheDocument();
    expect(screen.getByText('EXPEDITE_REBOOKING')).toBeInTheDocument();

    const checkNowBtn = screen.getByTestId('check-milestones-btn');
    expect(checkNowBtn).toHaveTextContent(/check now/i);

    await act(async () => {
      fireEvent.click(checkNowBtn);
    });

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/watchlist/check-milestones', { method: 'POST' });

    vi.unstubAllGlobals();
  });
});

