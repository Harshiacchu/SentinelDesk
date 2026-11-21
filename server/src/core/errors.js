export class AppError extends Error {
  constructor(message, status = 500) {
    super(message);
    this.name = this.constructor.name;
    this.status = status;
  }
}
export class ValidationError extends AppError {
  constructor(message) { super(message, 400); }
}
export class NotFoundError extends AppError {
  constructor(what) { super(`${what} not found`, 404); }
}
export class UpstreamError extends AppError {
  constructor(service, cause) { super(`${service} failed: ${cause?.message ?? cause}`, 502); }
}
export class NotImplementedError extends Error {
  constructor(cls, method) { super(`${cls}.${method}() must be implemented`); }
}
