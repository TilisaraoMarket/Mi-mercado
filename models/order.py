class Orden(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(50), default='pendiente')
    total = db.Column(db.Float, nullable=False, default=0)
    items = db.relationship('ItemOrden', backref='orden', lazy=True)

    def __init__(self, usuario_id, estado='pendiente'):
        self.usuario_id = usuario_id
        self.estado = estado
        self._hashcode = -1  # For caching hash value
        
    def calcular_total(self):
        """Calculate order total using timedelta for time-based pricing if needed"""
        total = sum(item.cantidad * item.precio_unitario for item in self.items)
        self.total = float(total)
        return self.total
        
    def tiempo_transcurrido(self):
        """Calculate elapsed time since order creation"""
        if not self.fecha_creacion:
            return None
        return datetime.utcnow() - self.fecha_creacion
        
    def esta_vencida(self, limite_horas=24):
        """Check if order is expired based on time limit"""
        if not self.fecha_creacion:
            return False
        tiempo = self.tiempo_transcurrido()
        return tiempo and tiempo > timedelta(hours=limite_horas)

    def __eq__(self, other):
        if not isinstance(other, Orden):
            return NotImplemented
        return (self.id == other.id and 
                self.fecha_creacion == other.fecha_creacion)

    def __hash__(self):
        if self._hashcode == -1:
            self._hashcode = hash((self.id, self.fecha_creacion))
        return self._hashcode