# 🚀 ADVANCED FEATURES IMPLEMENTATION GUIDE

**Complete step-by-step instructions to add all missing management features**

---

## 📋 TABLE OF CONTENTS

1. [Quick Start](#quick-start)
2. [Feature 1: AI Decision Dashboard](#feature-1-ai-decision-dashboard)
3. [Feature 2: Fraud Control Panel](#feature-2-fraud-control-panel)
4. [Feature 3: Dynamic Pricing Control](#feature-3-dynamic-pricing-control)
5. [Feature 4: Demand Forecast Dashboard](#feature-4-demand-forecast-dashboard)
6. [Feature 5: AI Insights](#feature-5-ai-insights)
7. [Testing Checklist](#testing-checklist)

---

## ⚡ QUICK START

### Step 1: Copy the Helper Functions
```bash
# Copy this file into your project:
ml_models/advanced_management.py
```

### Step 2: Add Routes to Manager Blueprint
In `routes/manager.py`, add all the imports and routes from `ADVANCED_ROUTES_TEMPLATE.py`

### Step 3: Create Templates
Create these new HTML files:
- `templates/manager/ai_decision_dashboard.html`
- `templates/manager/pricing_control.html`
- `templates/manager/demand_forecast.html`
- `templates/manager/ai_insights.html`

### Step 4: Test
Navigate to:
- `/manager/ai-decision`
- `/manager/pricing-control`
- `/manager/demand-forecast`
- `/manager/ai-insights`

---

## 🔥 FEATURE 1: AI DECISION DASHBOARD

### What It Does
- Shows fraudulent/suspicious bookings in real-time
- Displays risk levels (🟢 LOW / 🟡 MEDIUM / 🔴 HIGH)
- Provides AI-generated fraud explanations
- Allows manager to approve, block, or verify bookings

### Implementation Steps

#### Step 1.1: Add Helper Functions ✓ (Already Done)
```python
# File: ml_models/advanced_management.py
explain_fraud_reasons()
get_fraud_risk_level()
get_fraud_action_recommendation()
```

#### Step 1.2: Add Route to manager.py
```python
@manager_bp.route("/manager/ai-decision")
@manager_required
def ai_decision_dashboard():
    # See ADVANCED_ROUTES_TEMPLATE.py for full code
```

#### Step 1.3: Create Template
**File:** `templates/manager/ai_decision_dashboard.html`

```html
{% extends "base.html" %}
{% block title %}AI Decision Dashboard{% endblock %}
{% block content %}

<div class="container mt-4">
    <h1>🤖 AI Decision Center</h1>
    
    <!-- KPI Cards -->
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="card bg-danger text-white">
                <div class="card-body">
                    <h5>🔴 Requires Block</h5>
                    <h3>{{ block_count }}</h3>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card bg-warning text-dark">
                <div class="card-body">
                    <h5>🟡 Needs Review</h5>
                    <h3>{{ review_count }}</h3>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card bg-success text-white">
                <div class="card-body">
                    <h5>🟢 Safe Bookings</h5>
                    <h3>{{ safe_count }}</h3>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card bg-info text-white">
                <div class="card-body">
                    <h5>📊 Total Suspicious</h5>
                    <h3>{{ total_suspicious }}</h3>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Bookings Table -->
    <div class="card">
        <div class="card-header">
            <h5>Fraudulent Bookings (Sorted by Risk)</h5>
        </div>
        <div class="card-body">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Risk Level</th>
                        <th>Guest</th>
                        <th>Room Type</th>
                        <th>Amount</th>
                        <th>Fraud Score</th>
                        <th>Explanations</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {% for booking in fraudulent_bookings %}
                    <tr>
                        <td>
                            <span style="font-size: 1.5em;">{{ booking.risk_level.emoji }}</span>
                            <strong>{{ booking.risk_level.level }}</strong>
                        </td>
                        <td>{{ booking.first_name }} {{ booking.last_name }}</td>
                        <td>{{ booking.room_type }}</td>
                        <td>₹{{ booking.total_amount }}</td>
                        <td>{{ booking.fraud_score }}%</td>
                        <td>
                            <ul style="margin: 0; padding-left: 20px;">
                                {% for reason in booking.fraud_explanations %}
                                <li style="font-size: 0.9em;">{{ reason }}</li>
                                {% endfor %}
                            </ul>
                        </td>
                        <td>
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-success" onclick="fraudAction('{{ booking.booking_id }}', 'approve')">
                                    ✓ Approve
                                </button>
                                <button class="btn btn-warning" onclick="fraudAction('{{ booking.booking_id }}', 'verify')">
                                    ? Verify
                                </button>
                                <button class="btn btn-danger" onclick="fraudAction('{{ booking.booking_id }}', 'block')">
                                    ✕ Block
                                </button>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
function fraudAction(bookingId, action) {
    const notes = prompt(`Enter notes for ${action}:`);
    if (!notes) return;
    
    fetch(`/api/manager/fraud/${bookingId}/action`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrf_token]').value
        },
        body: JSON.stringify({action, notes})
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) {
            alert(d.message);
            location.reload();
        }
    });
}
</script>

{% endblock %}
```

---

## 🛡️ FEATURE 2: FRAUD CONTROL PANEL

### What It Does
- Deep-dive into fraud detection logic
- Shows which fraud rules triggered
- Displays rule-specific explanations
- Provides recommended action

### Implementation Steps

#### Step 2.1: Add API Endpoint
In `routes/manager.py`, add:
```python
@manager_bp.route("/api/manager/fraud/<booking_id>/details")
@manager_required
def fraud_booking_details(booking_id):
    # Returns detailed fraud analysis
```

#### Step 2.2: Update AI Decision Dashboard Template
Add a modal to show detailed fraud info:

```html
<!-- In ai_decision_dashboard.html -->
<div class="modal" id="fraudModal">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5>🔍 Fraud Analysis Details</h5>
                <button type="button" class="close" data-dismiss="modal">&times;</button>
            </div>
            <div class="modal-body" id="fraudDetails">
                <!-- Loaded dynamically -->
            </div>
        </div>
    </div>
</div>

<script>
function showFraudDetails(bookingId) {
    fetch(`/api/manager/fraud/${bookingId}/details`)
        .then(r => r.json())
        .then(data => {
            let html = `
                <p><strong>Fraud Score:</strong> ${data.fraud_analysis.score}%</p>
                <p><strong>Risk Level:</strong> ${data.fraud_analysis.risk_level.level}</p>
                <h6>Why This Booking is Flagged:</h6>
                <ul>
                    ${data.fraud_analysis.explanations.map(e => `<li>${e}</li>`).join('')}
                </ul>
            `;
            document.getElementById('fraudDetails').innerHTML = html;
            $('#fraudModal').modal('show');
        });
}
</script>
```

---

## 💰 FEATURE 3: DYNAMIC PRICING CONTROL

### What It Does
- Shows base price vs AI-calculated price
- Explains why price changed
- Allows manager to override prices
- Logs all price overrides

### Implementation Steps

#### Step 3.1: Add Route
```python
@manager_bp.route("/manager/pricing-control")
@manager_required
def pricing_control_dashboard():
    # See ADVANCED_ROUTES_TEMPLATE.py
```

#### Step 3.2: Create Template
**File:** `templates/manager/pricing_control.html`

```html
{% extends "base.html" %}
{% block title %}Dynamic Pricing Control{% endblock %}
{% block content %}

<div class="container mt-4">
    <h1>💰 Dynamic Pricing Control</h1>
    <p>Occupancy Rate: <strong>{{ occupancy_rate }}%</strong></p>
    
    <div class="row">
        {% for room in pricing_data %}
        <div class="col-md-6 mb-4">
            <div class="card">
                <div class="card-body">
                    <h5>{{ room.room_type }} - Room {{ room.room_number }}</h5>
                    
                    <table class="table table-sm">
                        <tr>
                            <td><strong>Base Price:</strong></td>
                            <td><strong>₹{{ room.base_price }}</strong></td>
                        </tr>
                        <tr>
                            <td>AI Suggested Price:</td>
                            <td>₹{{ room.ai_price }}</td>
                        </tr>
                        <tr>
                            <td>Current Price:</td>
                            <td>₹{{ room.current_price }}</td>
                        </tr>
                        <tr>
                            <td><strong>Price Change:</strong></td>
                            <td>{{ room.price_explanation.direction }}</td>
                        </tr>
                    </table>
                    
                    <div class="alert alert-info">
                        <strong>Why Price {{ room.price_explanation.direction.lower() }}:</strong>
                        <ul style="margin: 0; padding-left: 20px;">
                            {% for reason in room.price_explanation.detailed_reasons %}
                            <li>{{ reason }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                    
                    <button class="btn btn-primary" onclick="overridePrice('{{ room.room_id }}')">
                        ✎ Override Price
                    </button>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
</div>

<script>
function overridePrice(roomId) {
    const newPrice = prompt("Enter new price (₹):");
    if (!newPrice) return;
    
    const reason = prompt("Reason for override:");
    
    fetch(`/api/manager/pricing/${roomId}/override`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrf_token]').value
        },
        body: JSON.stringify({price: parseFloat(newPrice), reason})
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) {
            alert(d.message);
            location.reload();
        }
    });
}
</script>

{% endblock %}
```

---

## 📈 FEATURE 4: DEMAND FORECAST DASHBOARD

### What It Does
- Shows 30-day occupancy forecast
- Highlights peak and low demand days
- Provides AI-generated business suggestions
- Recommends discount periods

### Implementation Steps

#### Step 4.1: Add Route
```python
@manager_bp.route("/manager/demand-forecast")
@manager_required
def demand_forecast_dashboard():
    # See ADVANCED_ROUTES_TEMPLATE.py
```

#### Step 4.2: Create Template with Chart
**File:** `templates/manager/demand_forecast.html`

```html
{% extends "base.html" %}
{% block title %}Demand Forecast{% endblock %}
{% block content %}

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<div class="container mt-4">
    <h1>📈 30-Day Demand Forecast</h1>
    
    <!-- Chart -->
    <div class="card mb-4">
        <div class="card-body">
            <canvas id="forecastChart" height="80"></canvas>
        </div>
    </div>
    
    <!-- Suggestions -->
    <div class="alert alert-info">
        <h5>🎯 AI Business Suggestions:</h5>
        <ul>
            {% for suggestion in suggestions.recommendations %}
            <li><strong>{{ suggestion }}</strong></li>
            {% endfor %}
        </ul>
    </div>
    
    <!-- Peak/Low Days -->
    <div class="row">
        <div class="col-md-6">
            <div class="card border-success">
                <div class="card-header bg-success text-white">
                    <h5>🔥 High Demand Days ({{ suggestions.peak_days|length }})</h5>
                </div>
                <div class="card-body">
                    {% for day in suggestions.peak_days %}
                    <span class="badge badge-success">{{ day }}</span>
                    {% endfor %}
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card border-warning">
                <div class="card-header bg-warning text-dark">
                    <h5>❄️ Low Demand Days ({{ suggestions.low_days|length }})</h5>
                </div>
                <div class="card-body">
                    {% for day in suggestions.low_days %}
                    <span class="badge badge-warning">{{ day }}</span>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
</div>

<script>
const forecastData = {{ forecast_data|tojson }};
const dates = forecastData.map(d => d.date);
const occupancies = forecastData.map(d => d.occupancy_pct);

const ctx = document.getElementById('forecastChart').getContext('2d');
new Chart(ctx, {
    type: 'line',
    data: {
        labels: dates,
        datasets: [{
            label: 'Predicted Occupancy %',
            data: occupancies,
            borderColor: '#f59e0b',
            backgroundColor: 'rgba(245, 158, 11, 0.1)',
            fill: true,
            tension: 0.4,
            pointBackgroundColor: occupancies.map(o => o > 70 ? '#10b981' : o < 40 ? '#ef4444' : '#3b82f6')
        }]
    },
    options: {
        responsive: true,
        plugins: {
            legend: {position: 'top'},
            title: {display: true, text: 'Occupancy Forecast'}
        },
        scales: {
            y: {min: 0, max: 100}
        }
    }
});
</script>

{% endblock %}
```

---

## 🎯 FEATURE 5: AI INSIGHTS

### What It Does
- Shows most booked room types
- Displays guest preferences by loyalty tier
- Lists popular amenities
- Provides trending insights

### Implementation Steps

#### Step 5.1: Add Route
```python
@manager_bp.route("/manager/ai-insights")
@manager_required
def ai_insights_dashboard():
    # See ADVANCED_ROUTES_TEMPLATE.py
```

#### Step 5.2: Create Template
**File:** `templates/manager/ai_insights.html`

```html
{% extends "base.html" %}
{% block title %}AI Insights{% endblock %}
{% block content %}

<div class="container mt-4">
    <h1>🎯 AI-Powered Analytics & Insights</h1>
    
    <!-- Room Popularity -->
    <div class="card mb-4">
        <div class="card-header">
            <h5>🏆 Room Popularity Analysis</h5>
        </div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-6">
                    <h6>Most Booked Rooms:</h6>
                    {% for room in room_popularity.most_booked %}
                    <div class="mb-2">
                        <strong>{{ room.room_type }}</strong>
                        <div class="progress">
                            <div class="progress-bar" style="width: {{ room.percentage }}%">
                                {{ room.count }} bookings ({{ room.percentage }}%)
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                <div class="col-md-6">
                    <h6>Least Booked Rooms:</h6>
                    {% for room in room_popularity.least_booked %}
                    <div class="mb-2">
                        <strong>{{ room.room_type }}</strong>
                        <div class="progress">
                            <div class="progress-bar bg-warning" style="width: {{ room.percentage }}%">
                                {{ room.count }} bookings ({{ room.percentage }}%)
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
    
    <!-- Guest Preferences -->
    <div class="card mb-4">
        <div class="card-header">
            <h5>👥 Guest Preferences by Tier</h5>
        </div>
        <div class="card-body">
            {% for tier, preferences in guest_preferences.tier_preferences.items() %}
            <div class="mb-3">
                <h6>{{ tier }} Members:</h6>
                <p>Prefer: <strong>{{ preferences|join(', ') }}</strong></p>
            </div>
            {% endfor %}
            
            {% for insight in guest_preferences.insights %}
            <div class="alert alert-info">💡 {{ insight }}</div>
            {% endfor %}
        </div>
    </div>
    
    <!-- Popular Amenities -->
    <div class="card">
        <div class="card-header">
            <h5>⭐ Most Requested Amenities</h5>
        </div>
        <div class="card-body">
            {% for amenity in popular_amenities.top_amenities %}
            <div class="mb-2">
                <strong>{{ amenity.amenity }}</strong>
                <span class="badge badge-info">{{ amenity.rooms }} rooms</span>
            </div>
            {% endfor %}
            
            {% for insight in popular_amenities.insights %}
            <div class="alert alert-success">⭐ {{ insight }}</div>
            {% endfor %}
        </div>
    </div>
</div>

{% endblock %}
```

---

## ✅ TESTING CHECKLIST

After implementing all features, test:

- [ ] **AI Decision Dashboard**
  - [ ] Loads without errors
  - [ ] Shows fraudulent bookings
  - [ ] Risk levels display correctly
  - [ ] Fraud explanations are clear
  - [ ] Approve/Block/Verify buttons work
  
- [ ] **Fraud Control Panel**
  - [ ] Modal shows fraud details
  - [ ] Detailed explanations appear
  - [ ] Actions are logged
  
- [ ] **Dynamic Pricing Dashboard**
  - [ ] Shows base vs AI prices
  - [ ] Price explanations are accurate
  - [ ] Override button works
  - [ ] Price changes logged
  
- [ ] **Demand Forecast**
  - [ ] Chart displays 30 days
  - [ ] Peak/low days highlighted
  - [ ] Suggestions are actionable
  
- [ ] **AI Insights**
  - [ ] Room popularity ranked correctly
  - [ ] Guest preferences split by tier
  - [ ] Amenities ranked by popularity

---

## 🚀 DEPLOYMENT CHECKLIST

Before going live:

1. [ ] Test all endpoints in browser
2. [ ] Verify database schema updated if needed
3. [ ] Check CSS/styling in responsive mode
4. [ ] Test fraud action logging
5. [ ] Verify price override logging
6. [ ] Check KPI calculations accuracy
7. [ ] Test with real booking data
8. [ ] Verify all AI explanations are clear
9. [ ] Check performance (no slow queries)
10. [ ] Document any custom changes

---

## 📞 QUICK REFERENCE

### File Locations
- Helper Functions: `ml_models/advanced_management.py`
- Route Template: `ADVANCED_ROUTES_TEMPLATE.py`
- Templates: `templates/manager/`

### Key Functions
- `explain_fraud_reasons()` - Fraud explanation
- `explain_pricing_change()` - Pricing explanation
- `get_demand_suggestions()` - Demand insights
- `analyze_room_popularity()` - Room analysis
- `get_popular_amenities()` - Amenity analysis

### Key Routes
- `/manager/ai-decision` - Fraud control
- `/manager/pricing-control` - Pricing dashboard
- `/manager/demand-forecast` - Forecast dashboard
- `/manager/ai-insights` - Analytics dashboard
- `/api/manager/kpis/live` - Live KPI API

---

**Last Updated:** April 3, 2026
**Status:** Ready for Implementation
