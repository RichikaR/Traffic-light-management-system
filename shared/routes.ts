import { z } from 'zod';
import { SimulationStateSchema, VehicleType } from './schema';

export const api = {
  simulation: {
    getState: {
      method: 'GET' as const,
      path: '/api/simulation/state',
      responses: {
        200: SimulationStateSchema,
      },
    },
    reset: {
      method: 'POST' as const,
      path: '/api/simulation/reset',
      responses: {
        200: SimulationStateSchema,
      },
    },
    toggle: {
      method: 'POST' as const,
      path: '/api/simulation/toggle',
      input: z.object({ running: z.boolean() }),
      responses: {
        200: z.object({ running: z.boolean() }),
      },
    },
    addVehicle: {
      method: 'POST' as const,
      path: '/api/simulation/vehicle',
      input: z.object({
        roadId: z.number(),
        type: VehicleType,
      }),
      responses: {
        201: z.object({ message: z.string() }),
      },
    },
  },
};

export function buildUrl(path: string, params?: Record<string, string | number>): string {
  let url = path;
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (url.includes(`:${key}`)) {
        url = url.replace(`:${key}`, String(value));
      }
    });
  }
  return url;
}
