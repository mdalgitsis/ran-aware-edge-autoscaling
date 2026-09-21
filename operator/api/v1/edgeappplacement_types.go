/*
Copyright 2025.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

package v1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// EDIT THIS FILE!  THIS IS SCAFFOLDING FOR YOU TO OWN!
// NOTE: json tags are required.  Any new fields you add must have json tags for the fields to be serialized.

// EdgeAppPlacementSpec defines the desired state of EdgeAppPlacement.
type EdgeAppPlacementSpec struct {
	// AppID identifies the application whose placement is being tracked.
	AppID      string    `json:"appId"`
	EdgeNodeID string    `json:"edgeNodeId"`
	Kafka      KafkaSpec `json:"kafka"`
}

type KafkaSpec struct {
	Broker  string       `json:"broker"`
	Topic   string       `json:"topic"`
	Message KafkaMessage `json:"message"`
}

type KafkaMessage struct {
	EventType string `json:"eventType"`
}

// EdgeAppPlacementStatus defines the observed state of EdgeAppPlacement.
type EdgeAppPlacementStatus struct {
	// LastNotifiedEdgeNodeID is the edge node the last notification announced.
	// Comparing it against Spec.EdgeNodeID is what makes a migration detectable
	// and the notification exactly-once.
	LastNotifiedEdgeNodeID string `json:"lastNotifiedEdgeNodeId,omitempty"`
	LastNotificationTime   string `json:"lastNotificationTime,omitempty"`
	KafkaNotificationSent  bool   `json:"kafkaNotificationSent,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status

// EdgeAppPlacement is the Schema for the edgeappplacements API.
type EdgeAppPlacement struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   EdgeAppPlacementSpec   `json:"spec,omitempty"`
	Status EdgeAppPlacementStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// EdgeAppPlacementList contains a list of EdgeAppPlacement.
type EdgeAppPlacementList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []EdgeAppPlacement `json:"items"`
}

func init() {
	SchemeBuilder.Register(&EdgeAppPlacement{}, &EdgeAppPlacementList{})
}
