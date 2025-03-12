class Pago(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    orden_id = db.Column(db.Integer, db.ForeignKey('orden.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    moneda = db.Column(db.String(3), default='ARS')
    estado = db.Column(db.String(20), nullable=False, default=EstadoPago.PENDIENTE.value)
    metodo_pago = db.Column(db.String(20), nullable=False)
    stripe_payment_intent_id = db.Column(db.String(100))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, usuario_id, orden_id, monto, metodo_pago):
        self.usuario_id = usuario_id
        self.orden_id = orden_id
        self.monto = monto
        self.metodo_pago = metodo_pago
        self._hashcode = -1

    def actualizar_estado(self, nuevo_estado):
        """Update payment status with timestamp"""
        self.estado = nuevo_estado
        self.fecha_actualizacion = datetime.utcnow()

    def tiempo_pendiente(self):
        """Calculate time spent in pending status"""
        if self.estado != EstadoPago.PENDIENTE.value:
            return None
        return datetime.utcnow() - self.fecha_creacion

    def esta_expirado(self, limite_horas=48):
        """Check if payment is expired"""
        if self.estado != EstadoPago.PENDIENTE.value:
            return False
        tiempo = self.tiempo_pendiente()
        return tiempo and tiempo > timedelta(hours=limite_horas)

    def __eq__(self, other):
        if not isinstance(other, Pago):
            return NotImplemented
        return (self.id == other.id and
                self.fecha_creacion == other.fecha_creacion)

    def __hash__(self):
        if self._hashcode == -1:
            self._hashcode = hash((self.id, self.fecha_creacion))
        return self._hashcode